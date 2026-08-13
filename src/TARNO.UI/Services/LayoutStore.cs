using TARNO.UI.Models;
using System;
using System.IO;
using System.Text.Json;

namespace TARNO.UI.Services;

/// <summary>
/// Liest und schreibt das Multi-Screen-/Lochbrett-Layout als JSON.
/// Speicherort: %LOCALAPPDATA%\TARNO\layout.json.
/// </summary>
public static class LayoutStore
{
    private const string DefaultLayoutFileName = "layout.json";

    public static string GetLayoutPath(string? profileName = null)
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string tarnoDir = Path.Combine(localAppData, "TARNO");
        if (!Directory.Exists(tarnoDir))
        {
            Directory.CreateDirectory(tarnoDir);
        }

        string fileName = string.IsNullOrWhiteSpace(profileName) || profileName == "Standard"
            ? DefaultLayoutFileName
            : $"layout_{SanitizeFileName(profileName)}.json";
        return Path.Combine(tarnoDir, fileName);
    }

    private static string SanitizeFileName(string profileName)
    {
        foreach (char c in System.IO.Path.GetInvalidFileNameChars())
        {
            profileName = profileName.Replace(c, '_');
        }
        return profileName.Trim();
    }

    public static MultiScreenLayoutModel Load(string? profileName = null)
    {
        try
        {
            string path = GetLayoutPath(profileName);
            if (File.Exists(path))
            {
                string json = File.ReadAllText(path);
                var layout = JsonSerializer.Deserialize<MultiScreenLayoutModel>(json);
                if (layout is not null)
                {
                    return layout;
                }
            }
        }
        catch
        {
            // Defaults.
        }
        return CreateDefaultLayout(profileName);
    }

    public static void Save(MultiScreenLayoutModel layout, string? profileName = null)
    {
        if (layout is null)
        {
            return;
        }
        try
        {
            string path = GetLayoutPath(profileName);
            string json = JsonSerializer.Serialize(layout, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(path, json);
        }
        catch
        {
            // Speichern ist best-effort.
        }
    }

    /// <summary>Liefert ein Standard-Layout (alle Panels im Hauptfenster).</summary>
    public static MultiScreenLayoutModel CreateDefaultLayout(string? profileName = null)
    {
        return new MultiScreenLayoutModel
        {
            ProfileName = profileName ?? "Standard",
            DisplayCount = 1,
            Panels = new()
            {
                new PanelLayoutModel { PanelId = "explorer", WindowIndex = 0, DisplayIndex = 0 },
                new PanelLayoutModel { PanelId = "coding", WindowIndex = 0, DisplayIndex = 0 },
                new PanelLayoutModel { PanelId = "terminal", WindowIndex = 0, DisplayIndex = 0 },
                new PanelLayoutModel { PanelId = "context", WindowIndex = 0, DisplayIndex = 0 },
                new PanelLayoutModel { PanelId = "chat", WindowIndex = 0, DisplayIndex = 0 },
            },
        };
    }
}
