using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using TARNO.UI.Models;

namespace TARNO.UI.Services;

/// <summary>
/// Liest und schreibt die persistierten Workspaces (%LOCALAPPDATA%\TARNO\workspaces.json).
/// Zentraler Speicherort für Workspace-Verwaltung und Sandbox-Validierung.
/// </summary>
public static class WorkspaceStore
{
    private const string WorkspacesFileName = "workspaces.json";

    public static string GetWorkspacesPath()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string tarnoDir = Path.Combine(localAppData, "TARNO");
        if (!Directory.Exists(tarnoDir))
        {
            Directory.CreateDirectory(tarnoDir);
        }
        return Path.Combine(tarnoDir, WorkspacesFileName);
    }

    public static List<Workspace> Load()
    {
        try
        {
            string path = GetWorkspacesPath();
            if (File.Exists(path))
            {
                string json = File.ReadAllText(path);
                var workspaces = JsonSerializer.Deserialize<List<Workspace>>(json);
                if (workspaces is not null)
                {
                    MigrateLegacyRoots(workspaces);
                    return workspaces;
                }
            }
        }
        catch
        {
            // Defaults beibehalten.
        }
        return new List<Workspace>();
    }

    private static void MigrateLegacyRoots(List<Workspace> workspaces)
    {
        foreach (var workspace in workspaces)
        {
            if (workspace.Folders.Count == 0 && !string.IsNullOrWhiteSpace(workspace.RootPath))
            {
                workspace.Folders.Add(new WorkspaceFolder
                {
                    Name = workspace.Name,
                    Path = workspace.RootPath,
                });
            }
        }
    }

    public static void Save(List<Workspace> workspaces)
    {
        try
        {
            string path = GetWorkspacesPath();
            string json = JsonSerializer.Serialize(workspaces, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(path, json);
        }
        catch
        {
            // Speichern ist best-effort; Fehler ignorieren.
        }
    }

    public static void Add(Workspace workspace)
    {
        var workspaces = Load();
        workspaces.Add(workspace);
        Save(workspaces);
    }

    public static void Remove(string id)
    {
        var workspaces = Load();
        workspaces.RemoveAll(w => w.Id == id);
        Save(workspaces);
    }

    public static void Update(Workspace workspace)
    {
        var workspaces = Load();
        int index = workspaces.FindIndex(w => w.Id == workspace.Id);
        if (index >= 0)
        {
            workspaces[index] = workspace;
            Save(workspaces);
        }
    }
}
