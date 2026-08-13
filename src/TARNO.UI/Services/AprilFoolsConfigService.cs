using System;
using System.IO;
using System.Text.Json;
using TARNO.UI.Models;
using TARNO.UI.ViewModels;

namespace TARNO.UI.Services;

/// <summary>
/// Lädt die April-Fools-Konfiguration und die passende Locale.
/// Prüft außerdem, ob der Modus aktiviert sein sollte (Datum, Command-Line, Setting).
/// </summary>
public static class AprilFoolsConfigService
{
    private const string ConfigFileName = "april_fools_config.json";
    private static readonly string _baseDir = AppContext.BaseDirectory;

    public static bool CommandLineOverride { get; set; }

    /// <summary>
    /// Lädt die zentrale Konfiguration aus Assets/AprilFools/april_fools_config.json.
    /// </summary>
    public static AprilFoolsConfig? LoadConfig()
    {
        try
        {
            string path = Path.Combine(_baseDir, "Assets", "AprilFools", ConfigFileName);
            if (!File.Exists(path))
            {
                InteractionLogger.Warn("APRILFOOLS", $"Config nicht gefunden: {path}");
                return null;
            }

            string json = File.ReadAllText(path);
            return JsonSerializer.Deserialize<AprilFoolsConfig>(json);
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("APRILFOOLS", $"Fehler beim Laden der April-Fools-Config: {ex.Message}");
            return null;
        }
    }

    /// <summary>
    /// Lädt die Locale-Datei (z. B. de_april_fools.json).
    /// </summary>
    public static AprilFoolsLocale? LoadLocale(string localeName)
    {
        try
        {
            string fileName = $"{localeName}.json";
            string path = Path.Combine(_baseDir, "Assets", "AprilFools", "locales", fileName);
            if (!File.Exists(path))
            {
                InteractionLogger.Warn("APRILFOOLS", $"Locale nicht gefunden: {path}");
                return null;
            }

            string json = File.ReadAllText(path);
            return JsonSerializer.Deserialize<AprilFoolsLocale>(json);
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("APRILFOOLS", $"Fehler beim Laden der April-Fools-Locale: {ex.Message}");
            return null;
        }
    }

    /// <summary>
    /// Ermittelt, ob der April-Fools-Modus jetzt aktiv sein soll.
    /// Reihenfolge: Command-Line-Override > Dev-Setting > Systemdatum.
    /// </summary>
    public static bool IsAprilFoolsEnabled(SettingsViewModel? settings)
    {
        if (CommandLineOverride)
        {
            return true;
        }

        if (settings?.AprilFoolsEnabled == true)
        {
            return true;
        }

        var config = LoadConfig();
        if (config is null)
        {
            return false;
        }

        try
        {
            var today = DateTime.Now;
            string current = today.ToString("MM-dd");
            return string.Equals(current, config.AutoEnableOnDate, StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            return false;
        }
    }
}
