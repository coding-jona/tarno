using Microsoft.UI.Xaml;
using System;
using System.Collections.Generic;
using System.Linq;

namespace TARNO.UI.Services;

/// <summary>
/// Verwaltet alle offenen TARNO-Fenster (Hauptfenster + sekundaere Panel-Fenster).
/// Sorgt fuer sauberes Schliessen beim App-Exit und liefert das aktive Fenster.
/// In Phase 14 erhaelt jedes Fenster einen Index, damit Drag-and-Drop Panels
/// eindeutig ihrer Herkunft zuordnen und in ein Ziel verschieben kann.
/// </summary>
public static class WindowStateCoordinator
{
    private static readonly List<Window> _windows = new();
    private static readonly Dictionary<Window, int> _windowToIndex = new();
    private static readonly Dictionary<int, Window> _indexToWindow = new();
    private static int _nextFreeIndex = 10;

    /// <summary>Hauptfenster der App (wird als erstes registriert).</summary>
    public static Window? MainWindow { get; private set; }

    public static IReadOnlyList<Window> Windows => _windows;

    /// <summary>Eindeutiger Index des Hauptfensters.</summary>
    public const int MainWindowIndex = 0;

    /// <summary>Registriert ein Fenster und weist optional einen festen Index zu.
    /// Ohne Index wird der naechste freie Index vergeben.</summary>
    public static int Register(Window window, bool isMain = false, int? fixedIndex = null)
    {
        if (window is null)
        {
            throw new ArgumentNullException(nameof(window));
        }

        if (_windows.Contains(window))
        {
            return _windowToIndex[window];
        }

        int index = fixedIndex ?? _nextFreeIndex++;
        _windows.Add(window);
        _windowToIndex[window] = index;
        _indexToWindow[index] = window;
        window.Closed += (s, e) => Unregister(window);

        if (isMain)
        {
            MainWindow = window;
        }

        return index;
    }

    public static void Unregister(Window window)
    {
        if (window is null)
        {
            return;
        }
        _windows.Remove(window);
        if (_windowToIndex.TryGetValue(window, out var index))
        {
            _windowToIndex.Remove(window);
            _indexToWindow.Remove(index);
        }
        if (MainWindow == window)
        {
            MainWindow = null;
        }
    }

    public static Window? GetWindowByIndex(int index)
    {
        _indexToWindow.TryGetValue(index, out var window);
        return window;
    }

    public static int? GetWindowIndex(Window window)
    {
        if (_windowToIndex.TryGetValue(window, out var index))
        {
            return index;
        }
        return null;
    }

    public static Window? GetWindowByXamlRoot(Microsoft.UI.Xaml.XamlRoot xamlRoot)
    {
        if (xamlRoot is null)
        {
            return null;
        }

        foreach (var window in _windows)
        {
            if (window.Content?.XamlRoot == xamlRoot)
            {
                return window;
            }
        }

        return null;
    }

    /// <summary>Schliesst alle registrierten Fenster ausser dem Hauptfenster.</summary>
    public static void CloseSecondaryWindows()
    {
        foreach (var window in _windows.ToList())
        {
            if (window != MainWindow)
            {
                try
                {
                    window.Close();
                }
                catch
                {
                    // Best-effort: Fenster kann bereits geschlossen sein.
                }
            }
        }
    }

    /// <summary>Schliesst alle Fenster (fuer App-Exit).</summary>
    public static void CloseAll()
    {
        foreach (var window in _windows.ToList())
        {
            try
            {
                window.Close();
            }
            catch
            {
                // Best-effort.
            }
        }
        _windows.Clear();
        _windowToIndex.Clear();
        _indexToWindow.Clear();
        MainWindow = null;
    }

    /// <summary>Aktives Fenster (zuletzt fokussiertes) oder das Hauptfenster.</summary>
    public static Window? GetActiveWindow()
    {
        // In unpackaged WinUI 3 gibt es keine einfache API fuer "aktives" Fenster.
        // Wir verwenden das Hauptfenster als XamlRoot-Quelle fuer Dialoge.
        return MainWindow ?? _windows.FirstOrDefault();
    }

    /// <summary>XamlRoot eines Fensters, an das Content-Dialoge gebunden werden koennen.</summary>
    public static Microsoft.UI.Xaml.XamlRoot? GetActiveXamlRoot()
    {
        var active = GetActiveWindow();
        return active?.Content?.XamlRoot;
    }
}
