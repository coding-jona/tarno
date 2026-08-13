using TARNO.UI.ViewModels;
using System;
using System.IO;
using System.Text.Json;

namespace TARNO.UI.Services;

/// <summary>
/// Liest und schreibt die persistierten App-Einstellungen (%LOCALAPPDATA%\TARNO\settings.json).
/// Zentraler Speicherort, damit MainViewModel (Startup) und SettingsPage (Bearbeitung)
/// dieselbe Datei ohne Duplikation ansprechen.
/// </summary>
public static class SettingsStore
{
    private const string SettingsFileName = "settings.json";

    public static string GetSettingsPath()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string tarnoDir = Path.Combine(localAppData, "TARNO");
        if (!Directory.Exists(tarnoDir))
        {
            Directory.CreateDirectory(tarnoDir);
        }
        return Path.Combine(tarnoDir, SettingsFileName);
    }

    public static SettingsViewModel Load()
    {
        try
        {
            string path = GetSettingsPath();
            if (File.Exists(path))
            {
                string json = File.ReadAllText(path);
                var settings = JsonSerializer.Deserialize<SettingsViewModel>(json);
                if (settings is not null)
                {
                    return settings;
                }
            }
        }
        catch
        {
            // Defaults beibehalten.
        }
        return new SettingsViewModel();
    }

    public static void Save(SettingsViewModel settings)
    {
        try
        {
            string path = GetSettingsPath();
            string json = JsonSerializer.Serialize(settings, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(path, json);
        }
        catch
        {
            // Speichern ist best-effort; Fehler ignorieren.
        }
    }
}
