using Microsoft.UI.Xaml;
using TARNO.UI.Services;
using System;
using Windows.Globalization;
using System.Diagnostics;
using System.IO;
using System.Threading;

namespace TARNO.UI;

/// <summary>
/// Provides application-specific behavior to supplement the default Application class.
/// </summary>
public partial class App : Application
{
    // Verhindert, dass ein zweiter App-Start ein zweites Backend spawnt (das
    // Doppel-Oeffnen-Problem: zwei UI-Prozesse, zwei Backend-Kindprozesse,
    // von denen einer den gRPC-Port verliert und beim Schliessen des
    // "falschen" Fensters das noch aktive Fenster kaputt zurueckliess).
    // Named Mutex statt AppInstance-API, da diese App unpackaged ist
    // (WindowsPackageType=None) und die MSIX-basierte Single-Instance-API
    // ohne Paket-Identitaet nicht zur Verfuegung steht.
    private const string SingleInstanceMutexName = "Global\\TARNO_UI_SingleInstance";
    private Mutex? _singleInstanceMutex;

    private Process? _backendProcess;
    private GlobalHotkeyService? _killSwitchHotkey;
    private GlobalHotkeyService? _muteHotkey;

    // Block 5, Phase 46 ("physischer Kill-Switch"): Strg+Alt+K beendet TARNO
    // sofort und vollstaendig, unabhaengig davon, was die KI gerade tut -
    // Human-in-the-Loop-Notausstieg fuer den Fall, dass sich die Autonomie-
    // Pipeline (siehe AutonomyMode) irgendwie verhaengt oder unerwuenscht
    // verhaelt. Funktioniert auch, wenn TARNO nicht das Vordergrundfenster ist.
    private const uint VK_K = 0x4B;

    // Strg+Alt+M schaltet das Mikrofon (Voice-Eingabe) um, ohne dass der
    // Nutzer in die VoicePage klicken muss.
    private const uint VK_M = 0x4D;

    // Installierte Apps unter Program Files haben als Standardnutzer kein
    // Schreibrecht auf ihr eigenes Installationsverzeichnis
    // (AppContext.BaseDirectory) - Logs dorthin schlagen dort fehl und
    // werden vom umgebenden try/catch lautlos verschluckt, was genau dann
    // jede Diagnose unmoeglich macht, wenn sie am dringendsten gebraucht
    // wird (z.B. wenn der Backend-Start selbst fehlschlaegt). LocalAppData
    // ist fuer jeden Nutzer immer beschreibbar, unabhaengig vom
    // Installationsort - gleiches Muster wie InteractionLogger.
    private static readonly string LogDirectory = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "TARNO", "logs");

    /// <summary>
    /// Initializes the singleton application object.
    /// </summary>
    public App()
    {
        // PrimaryLanguageOverride wird bereits in Program.cs vor
        // Application.Start gesetzt; dort ist der Resource-Context noch nicht
        // fixiert. Ein spaeteres Setzen in unpackaged WinUI 3 wirft
        // InvalidOperationException.
        this.InitializeComponent();
        UnhandledException += (s, e) =>
        {
            try
            {
                Directory.CreateDirectory(LogDirectory);
                File.AppendAllText(
                    Path.Combine(LogDirectory, "tarno_ui_crash.log"),
                    $"{DateTime.Now:O} {e.Exception}\n{e.Message}\n\n");
            }
            catch { }
        };
    }

    /// <summary>
    /// Invoked when the application is launched normally by the end user.
    /// </summary>
    /// <param name="args">Details about the launch request and process.</param>
    protected override void OnLaunched(LaunchActivatedEventArgs args)
    {
        _singleInstanceMutex = new Mutex(initiallyOwned: true, SingleInstanceMutexName, out var createdNew);
        if (!createdNew)
        {
            // Eine Instanz laeuft bereits - kein zweites Fenster, kein
            // zweites Backend. Der Mutex wird nicht freigegeben (bleibt
            // ungenutzt), damit kein Race mit der laufenden Instanz entsteht.
            Environment.Exit(0);
            return;
        }

        StartBackend();

        // The hologram orb lives inside VoicePage now (see VoicePage.xaml),
        // not as a separate always-on-top desktop window - see git history /
        // conversation notes for why the standalone-window approach was
        // abandoned (WebView2's windowed hosting mode does not compose with
        // layered-window transparency, so it rendered as an opaque black
        // circle instead of glass).
        m_window = new MainWindow();
        m_window.Closed += OnWindowClosed;
        m_window.Activate();

        RegisterKillSwitch();
        RegisterMuteHotkey();
    }

    private void RegisterKillSwitch()
    {
        try
        {
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(m_window);
            _killSwitchHotkey = new GlobalHotkeyService(hwnd, VK_K, ctrl: true, alt: true, shift: false);
            _killSwitchHotkey.HotkeyPressed += OnKillSwitchTriggered;
        }
        catch (Exception ex)
        {
            LogBackendEvent($"Kill-Switch-Hotkey konnte nicht registriert werden: {ex}");
        }
    }

    private void OnKillSwitchTriggered()
    {
        LogBackendEvent("Kill-Switch (Strg+Alt+K) ausgeloest - beende TARNO sofort.");
        KillBackendAndReleaseMutex();
        // Environment.Exit statt geordnetem WinUI-Shutdown: ein Kill-Switch
        // muss auch dann sofort greifen, wenn die App gerade irgendwo haengt
        // (z.B. eine blockierende LLM-Anfrage) - kein Warten auf einen
        // moeglicherweise nie kommenden geordneten Shutdown-Zyklus.
        Environment.Exit(1);
    }

    private void RegisterMuteHotkey()
    {
        var settings = (m_window as MainWindow)?.ViewModel.Settings ?? SettingsStore.Load();
        RegisterMuteHotkey(settings.MuteHotkey);
    }

    private void RegisterMuteHotkey(string? hotkeyString)
    {
        if (string.IsNullOrWhiteSpace(hotkeyString))
        {
            return;
        }
        if (!TryParseHotkey(hotkeyString, out uint vk, out bool ctrl, out bool alt, out bool shift))
        {
            LogBackendEvent($"Mute-Hotkey '{hotkeyString}' hat ein ungültiges Format.");
            return;
        }
        try
        {
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(m_window);
            _muteHotkey = new GlobalHotkeyService(hwnd, vk, ctrl: ctrl, alt: alt, shift: shift);
            _muteHotkey.HotkeyPressed += OnMuteHotkeyTriggered;
        }
        catch (Exception ex)
        {
            LogBackendEvent($"Mute-Hotkey '{hotkeyString}' konnte nicht registriert werden: {ex}");
        }
    }

    public void ReloadMuteHotkey()
    {
        _muteHotkey?.Dispose();
        _muteHotkey = null;
        RegisterMuteHotkey();
    }

    private static bool TryParseHotkey(string hotkey, out uint vk, out bool ctrl, out bool alt, out bool shift)
    {
        vk = 0;
        ctrl = false;
        alt = false;
        shift = false;
        var parts = hotkey.Split('+', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        foreach (var part in parts)
        {
            var upper = part.ToUpperInvariant();
            if (upper == "CTRL") { ctrl = true; continue; }
            if (upper == "ALT") { alt = true; continue; }
            if (upper == "SHIFT") { shift = true; continue; }
            if (part.Length == 1 && char.IsLetter(part[0]))
            {
                vk = (uint)char.ToUpperInvariant(part[0]);
                return true;
            }
        }
        return false;
    }

    private async void OnMuteHotkeyTriggered()
    {
        LogBackendEvent("Mute-Hotkey (Strg+Alt+M) ausgeloest.");
        if (m_window is MainWindow mainWindow)
        {
            try
            {
                await mainWindow.ViewModel.ToggleVoiceAsync();
            }
            catch (Exception ex)
            {
                LogBackendEvent($"Mute-Hotkey fehlgeschlagen: {ex}");
            }
        }
    }

    private void StartBackend()
    {
        string backendPath = Path.Combine(AppContext.BaseDirectory, "..", "tarno.exe");
        backendPath = Path.GetFullPath(backendPath);
        if (!File.Exists(backendPath))
        {
            // Entwicklungsumgebung: Backend muss manuell gestartet werden.
            return;
        }

        KillStaleBackendProcesses(backendPath);

        try
        {
            _backendProcess = new Process
            {
                StartInfo = new ProcessStartInfo
                {
                    FileName = backendPath,
                    // --backend: laeuft nur als gRPC-Server (tarno/__main__.py).
                    // Ohne dieses Flag faellt tarno.exe auf seinen dev-Default
                    // zurueck (winui_launcher.launch_winui - Python versucht,
                    // seinerseits eine WinUI.exe zu starten) und beendet sich
                    // sofort, da die dazu erwartete Dev-Verzeichnisstruktur im
                    // installierten Paket nicht existiert - das Backend startete
                    // dadurch nie, ohne jede sichtbare Fehlermeldung.
                    Arguments = "--backend",
                    WorkingDirectory = Path.GetDirectoryName(backendPath) ?? AppContext.BaseDirectory,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                }
            };
            _backendProcess.Start();

            // Kurzer Health-Check: ein Port-Konflikt oder fehlende Python-
            // Runtime im Zielsystem laesst den Kindprozess sofort wieder
            // abstuerzen. Ohne diesen Check wuerde die App "erfolgreich"
            // weiterlaufen, obwohl gar kein Backend mehr existiert.
            Thread.Sleep(300);
            if (_backendProcess.HasExited)
            {
                LogBackendEvent($"Backend-Prozess ist sofort nach dem Start beendet (Exit-Code {_backendProcess.ExitCode}) - moeglicherweise Port-Konflikt oder fehlende Abhaengigkeit.");
            }
        }
        catch (Exception ex)
        {
            LogBackendEvent($"Backend start failed: {ex}");
        }
    }

    private static void LogBackendEvent(string message)
    {
        try
        {
            Directory.CreateDirectory(LogDirectory);
            File.AppendAllText(
                Path.Combine(LogDirectory, "tarno_ui_backend.log"),
                $"{DateTime.Now:O} {message}\n");
        }
        catch { }
    }

    /// <summary>
    /// Beendet Backend-Leichen von einem vorherigen, unsauberen Beenden
    /// (z.B. Absturz der UI, bevor OnWindowClosed den Kindprozess killen
    /// konnte) - sonst haelt die Leiche den gRPC-Port und der neue,
    /// frisch gestartete Backend-Prozess scheitert beim Binden.
    /// </summary>
    private void KillStaleBackendProcesses(string backendPath)
    {
        try
        {
            foreach (var proc in Process.GetProcessesByName("tarno"))
            {
                using (proc)
                {
                    try
                    {
                        if (string.Equals(proc.MainModule?.FileName, backendPath, StringComparison.OrdinalIgnoreCase))
                        {
                            proc.Kill(entireProcessTree: true);
                            proc.WaitForExit(3000);
                        }
                    }
                    catch
                    {
                        // Kein Zugriff auf MainModule (z.B. anderer Nutzer/Elevation)
                        // oder Prozess ist zwischen Enumeration und Kill schon weg -
                        // in beiden Faellen ignorieren und mit dem Start fortfahren.
                    }
                }
            }
        }
        catch
        {
            // Process.GetProcessesByName kann in seltenen Faellen selbst
            // fehlschlagen - darf den App-Start nicht verhindern.
        }
    }

    private void OnWindowClosed(object sender, WindowEventArgs args)
    {
        _muteHotkey?.Dispose();
        _killSwitchHotkey?.Dispose();
        WindowStateCoordinator.CloseSecondaryWindows();
        KillBackendAndReleaseMutex();
    }

    private void KillBackendAndReleaseMutex()
    {
        try
        {
            if (_backendProcess?.HasExited == false)
            {
                _backendProcess.Kill(entireProcessTree: true);
            }
        }
        catch { }

        try
        {
            _singleInstanceMutex?.ReleaseMutex();
            _singleInstanceMutex?.Dispose();
        }
        catch { }
    }

    private Window? m_window;

    /// <summary>Erlaubt Seiten, an das Hauptfenster-Handle zu kommen (z.B. für
    /// FileOpenPicker, das in WinUI 3 Desktop-Apps eine Fenster-Assoziation
    /// via InitializeWithWindow braucht).</summary>
    public static Window? MainWindow => (Current as App)?.m_window;
}
