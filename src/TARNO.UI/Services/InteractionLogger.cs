using System;
using System.IO;

namespace TARNO.UI.Services;

/// <summary>
/// Schreibt UI-Interaktionen (Klicks, Navigation, Tasten) in eine separate Log-Datei.
/// Orientiert sich an Minecraft-Logs: zeitgestempelt, eine Zeile pro Ereignis.
/// </summary>
public static class InteractionLogger
{
    private static readonly string LogDirectory;
    private static readonly string LogFilePath;

    // War frueher SemaphoreSlim + Task.ContinueWith (fire-and-forget): wenn
    // WaitAsync(1000) mal ablief, ohne die Sperre zu bekommen, rief der
    // Continuation-Block Lock.Release() trotzdem im finally auf - das wirft
    // eine SemaphoreFullException, die als unbeobachtete Task-Exception
    // still verschluckt wird, die Sperre aber dauerhaft verklemmt zurueckliess.
    // Ergebnis: Nach der ersten Timing-Kollision loggte die App fuer den
    // Rest der Session ueberhaupt nichts mehr, ohne jede Fehlermeldung -
    // live so vorgefunden (keine einzige neue Zeile ueber mehrere
    // Build/Test-Zyklen hinweg). Ein simples synchrones Lock fuer eine
    // Textzeile ist unproblematisch und kann so nicht verklemmen.
    private static readonly object Lock = new();

    static InteractionLogger()
    {
        LogDirectory = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "TARNO",
            "logs");
        LogFilePath = Path.Combine(LogDirectory, "ui_interactions.log");

        try
        {
            Directory.CreateDirectory(LogDirectory);
        }
        catch
        {
            // Best-effort: Logging darf Start nicht verhindern.
        }
    }

    /// <summary>
    /// Schreibt einen Eintrag in das UI-Interaktions-Log.
    /// Format: [ISO-Zeit] [LEVEL] [Bereich] Nachricht
    /// </summary>
    public static void Log(string level, string area, string message)
    {
        var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff} [{level}] [{area}] {message}";

        lock (Lock)
        {
            try
            {
                File.AppendAllText(LogFilePath, line + Environment.NewLine);
            }
            catch
            {
                // Loggen ist best-effort; bei I/O-Fehlern still ignorieren.
            }
        }
    }

    public static void Info(string area, string message) => Log("INFO", area, message);
    public static void Warn(string area, string message) => Log("WARN", area, message);
    public static void Error(string area, string message) => Log("ERROR", area, message);

    /// <summary>
    /// Kurzhilfe für Klick-Ereignisse: [INFO] [UI] Button 'X' clicked on Page 'Y'
    /// </summary>
    public static void Click(string page, string elementName)
    {
        Info("UI", $"Button '{elementName}' clicked on Page '{page}'");
    }

    /// <summary>
    /// Loggt Seiten-Navigation.
    /// </summary>
    public static void Navigate(string fromPage, string toPage)
    {
        Info("NAV", $"Navigated from '{fromPage}' to '{toPage}'");
    }
}
