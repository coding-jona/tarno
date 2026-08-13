using System;
using System.IO;
using System.Text.Json;

namespace TARNO.UI.Services;

/// <summary>
/// Persistiert UI-Zustände wie aktuelle Seite, Sidebar-Modus und aktiver Chat.
/// Speicherort: %LOCALAPPDATA%\TARNO\ui_state.json
/// </summary>
public static class AppStateStore
{
    private const string StateFileName = "ui_state.json";

    public static string GetStatePath()
    {
        string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string tarnoDir = Path.Combine(localAppData, "TARNO");
        if (!Directory.Exists(tarnoDir))
        {
            Directory.CreateDirectory(tarnoDir);
        }
        return Path.Combine(tarnoDir, StateFileName);
    }

    public static AppState Load()
    {
        try
        {
            string path = GetStatePath();
            if (File.Exists(path))
            {
                string json = File.ReadAllText(path);
                var state = JsonSerializer.Deserialize<AppState>(json);
                if (state is not null)
                {
                    return state;
                }
            }
        }
        catch
        {
            // Defaults bei Korruption.
        }
        return new AppState();
    }

    public static void Save(AppState state)
    {
        try
        {
            string path = GetStatePath();
            state.UpdatedAt = DateTimeOffset.Now;
            string json = JsonSerializer.Serialize(state, new JsonSerializerOptions { WriteIndented = true });
            File.WriteAllText(path, json);
        }
        catch
        {
            // Best-effort.
        }
    }
}

public class AppState
{
    public string? SelectedPage { get; set; }
    public string? SidebarMode { get; set; }
    public string? ActiveChatId { get; set; }
    public string? ActiveWorkspaceId { get; set; }
    public DateTimeOffset UpdatedAt { get; set; } = DateTimeOffset.Now;
}
