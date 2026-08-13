using System;
using System.IO;

namespace TARNO.UI.Services;

/// <summary>
/// Persistiert, ob die Hauptseitenleiste eingeklappt ist
/// (%LOCALAPPDATA%\TARNO\sidebar_collapsed.txt). Eigene, winzige Datei statt
/// Erweiterung des grossen Settings-Speichers, um diese Änderung isoliert zu
/// halten.
/// </summary>
public static class SidebarStateStore
{
    private const string FileName = "sidebar_collapsed.txt";

    public static bool LoadCollapsed()
    {
        try
        {
            string path = GetPath();
            if (File.Exists(path))
            {
                return File.ReadAllText(path).Trim() == "1";
            }
        }
        catch
        {
            // Default: aufgeklappt.
        }
        return false;
    }

    public static void SaveCollapsed(bool collapsed)
    {
        try
        {
            File.WriteAllText(GetPath(), collapsed ? "1" : "0");
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
