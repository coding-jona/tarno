using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Validiert und führt Dateioperationen innerhalb der Workspace-Sandbox aus.
/// </summary>
public static class FileAccessService
{
    private const int MaxReadSizeBytes = 1 * 1024 * 1024; // 1 MB

    /// <summary>Liest eine Textdatei innerhalb des Workspaces, falls erlaubt.</summary>
    public static async Task<string?> ReadFileAsync(string path, Workspace workspace)
    {
        if (!IsPathAllowed(path, workspace))
        {
            return null;
        }

        try
        {
            var info = new FileInfo(path);
            if (!info.Exists || info.Length > MaxReadSizeBytes)
            {
                return null;
            }
            using var reader = new StreamReader(path);
            return await reader.ReadToEndAsync().ConfigureAwait(false);
        }
        catch
        {
            return null;
        }
    }

    /// <summary>Schreibt Text atomisch in eine Datei innerhalb des Workspaces.</summary>
    public static async Task<bool> WriteFileAsync(string path, string content, Workspace workspace)
    {
        if (!IsPathAllowed(path, workspace))
        {
            return false;
        }

        try
        {
            string fullPath = Path.GetFullPath(path);
            string? directory = Path.GetDirectoryName(fullPath);
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }

            string tempPath = fullPath + ".tmp";
            await File.WriteAllTextAsync(tempPath, content).ConfigureAwait(false);
            File.Replace(tempPath, fullPath, fullPath + ".bak");
            return true;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>Sucht Dateien im Workspace, die Include-/Exclude-Patterns erfüllen.</summary>
    public static List<string> SearchFiles(Workspace workspace)
    {
        if (workspace.Folders.Count == 0)
        {
            return new List<string>();
        }

        var result = new List<string>();
        foreach (var folder in workspace.Folders)
        {
            if (string.IsNullOrWhiteSpace(folder.Path) || !Directory.Exists(folder.Path))
            {
                continue;
            }
            var root = new DirectoryInfo(Path.GetFullPath(folder.Path));
            foreach (var file in root.EnumerateFiles("*", SearchOption.AllDirectories))
            {
                string relative = file.FullName.Substring(root.FullName.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
                string relativeSlash = relative.Replace(Path.DirectorySeparatorChar, '/').Replace(Path.AltDirectorySeparatorChar, '/');
                if (IsRelativeAllowed(relativeSlash, workspace))
                {
                    result.Add(file.FullName);
                }
            }
        }
        return result;
    }

    /// <summary>Prüft, ob ein absoluter Pfad innerhalb eines Workspace-Roots liegt und
    /// von Include-/Exclude-Patterns erlaubt ist.</summary>
    public static bool IsPathAllowed(string path, Workspace workspace)
    {
        if (workspace.Folders.Count == 0 || string.IsNullOrWhiteSpace(path))
        {
            return false;
        }

        string fullPath;
        try
        {
            fullPath = Path.GetFullPath(path);
        }
        catch
        {
            return false;
        }

        foreach (var folder in workspace.Folders)
        {
            if (string.IsNullOrWhiteSpace(folder.Path))
            {
                continue;
            }

            string fullRoot;
            try
            {
                fullRoot = Path.GetFullPath(folder.Path);
            }
            catch
            {
                continue;
            }

            if (!fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            string relativePath = fullPath.Substring(fullRoot.Length).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            string relativeSlash = relativePath.Replace(Path.DirectorySeparatorChar, '/').Replace(Path.AltDirectorySeparatorChar, '/');

            // Exclude-Patterns prüfen (höchste Priorität).
            foreach (var pattern in workspace.ExcludePatterns)
            {
                if (MatchesGlob(relativeSlash, pattern))
                {
                    return false;
                }
            }

            // Mindestens ein Include-Pattern muss passen.
            foreach (var pattern in workspace.IncludePatterns)
            {
                if (MatchesGlob(relativeSlash, pattern))
                {
                    return true;
                }
            }
        }

        return false;
    }

    /// <summary>Prüft, ob ein relativer Pfad (mit /-Separatoren) von den
    /// Include-/Exclude-Patterns des Workspaces erlaubt ist.</summary>
    private static bool IsRelativeAllowed(string relativeSlash, Workspace workspace)
    {
        foreach (var pattern in workspace.ExcludePatterns)
        {
            if (MatchesGlob(relativeSlash, pattern))
            {
                return false;
            }
        }

        foreach (var pattern in workspace.IncludePatterns)
        {
            if (MatchesGlob(relativeSlash, pattern))
            {
                return true;
            }
        }

        return false;
    }

    /// <summary>Konvertiert eine einfache Glob-Notation in Regex.
    /// Unterstützt: *, **, ?, /-Separatoren, Datei- und Verzeichnis-Patterns.</summary>
    private static bool MatchesGlob(string path, string pattern)
    {
        if (string.IsNullOrWhiteSpace(pattern))
        {
            return false;
        }

        string p = pattern.Trim().Replace(Path.DirectorySeparatorChar, '/').Replace(Path.AltDirectorySeparatorChar, '/');

        // ** am Anfang: matcht in beliebigen Unterverzeichnissen.
        if (p.StartsWith("**/"))
        {
            string suffix = p.Substring(3);
            return MatchRelative(path, suffix, allowPrefix: true);
        }

        return MatchRelative(path, p, allowPrefix: false);
    }

    private static bool MatchRelative(string path, string pattern, bool allowPrefix)
    {
        string escaped = Regex.Escape(pattern)
            .Replace(@"\*\*", ".*")      // ** matcht über beliebig viele Pfadsegmente
            .Replace(@"\*", "[^/]*")     // * matcht ein Segment
            .Replace(@"\?", "[^/]");     // ? matcht ein Zeichen

        string prefix = allowPrefix ? "(^|(.*/))" : "^";
        string suffix = pattern.EndsWith("/") ? "/" : "($|/)";
        string regex = $"{prefix}{escaped}{suffix}";

        try
        {
            return Regex.IsMatch(path, regex, RegexOptions.IgnoreCase);
        }
        catch
        {
            return false;
        }
    }
}
