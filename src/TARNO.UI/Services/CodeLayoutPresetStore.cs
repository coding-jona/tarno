using System;
using System.IO;

namespace TARNO.UI.Services;

/// <summary>
/// Persistiert die gewaehlte Layout-Vorlage der CodeWorkspacePage
/// (%LOCALAPPDATA%\TARNO\code_layout.txt). Bewusst als eigene, winzige Datei
/// statt in den grossen Settings/Layout-Speichern untergebracht, um diese
/// Aenderung nicht mit unabhaengigem Bestandscode zu verflechten.
/// </summary>
public static class CodeLayoutPresetStore
{
    private const string FileName = "code_layout.txt";

    public static string Load(string fallback)
    {
        try
        {
            string path = GetPath();
            if (File.Exists(path))
            {
                string value = File.ReadAllText(path).Trim();
                if (!string.IsNullOrWhiteSpace(value))
                {
                    return value;
                }
            }
        }
        catch
        {
            // Defaults.
        }
        return fallback;
    }

    public static void Save(string presetName)
    {
        try
        {
            File.WriteAllText(GetPath(), presetName);
        }
        catch
        {
            // Speichern ist best-effort.
        }
    }

    private static string GetPath()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string tarnoDir = Path.Combine(localAppData, "TARNO");
        if (!Directory.Exists(tarnoDir))
        {
            Directory.CreateDirectory(tarnoDir);
        }
        return Path.Combine(tarnoDir, FileName);
    }
}
