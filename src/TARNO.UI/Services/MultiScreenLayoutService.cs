using TARNO.UI.Models;
using TARNO.UI.ViewModels;
using Microsoft.UI.Windowing;
using System;
using System.Collections.Generic;
using System.Linq;
using Windows.Graphics;

namespace TARNO.UI.Services;

/// <summary>
/// Erkennt Monitore und berechnet Fenster-Positionen fuer den Multi-Screen-Modus.
/// Nutzt ausschließlich Microsoft.UI.Windowing APIs (keine neuen Abhaengigkeiten).
/// </summary>
public static class MultiScreenLayoutService
{
    /// <summary>Liefert alle erkannten DisplayAreas (Monitore).</summary>
    public static IReadOnlyList<DisplayArea> GetDisplays()
    {
        return DisplayArea.FindAll() ?? new List<DisplayArea>();
    }

    /// <summary>Berechnet, wie viele Bildschirme im Multi-Screen-Modus genutzt werden sollen (1-3).</summary>
    public static int ResolveScreenCount(SettingsViewModel settings)
    {
        var displays = GetDisplays();
        int available = displays.Count;
        if (!settings.MultiScreenEnabled)
        {
            return 1;
        }
        if (settings.AutoScreenSplit)
        {
            return Math.Clamp(available, 1, 3);
        }
        return Math.Clamp(settings.ManualScreenCount, 1, Math.Min(available, 3));
    }

    /// <summary>Arbeitsbereich (sicherer Bereich ohne Taskleiste) des n-ten Bildschirms.</summary>
    public static RectInt32 GetWorkArea(int displayIndex)
    {
        var displays = GetDisplays();
        if (displayIndex < 0 || displayIndex >= displays.Count)
        {
            return default;
        }
        return displays[displayIndex].WorkArea;
    }

    /// <summary>Sicheres Platzieren eines Fensters im Work-Area eines Bildschirms.</summary>
    public static void PositionWindowOnDisplay(Microsoft.UI.Windowing.AppWindow appWindow, int displayIndex)
    {
        var displays = GetDisplays();
        if (displayIndex < 0 || displayIndex >= displays.Count)
        {
            return;
        }

        var workArea = displays[displayIndex].WorkArea;
        if (workArea.X == 0 && workArea.Y == 0 && workArea.Width == 0 && workArea.Height == 0)
        {
            return;
        }

        appWindow.MoveAndResize(workArea, displays[displayIndex]);
    }

    /// <summary>Platziert ein Fenster anhand eines gespeicherten RectModels.</summary>
    public static void PositionWindow(Microsoft.UI.Windowing.AppWindow appWindow, RectModel bounds)
    {
        if (bounds is null)
        {
            return;
        }

        var displays = GetDisplays();
        var target = new RectInt32(bounds.X, bounds.Y, bounds.Width, bounds.Height);
        int displayIndex = FindDisplayForPoint(new PointInt32(target.X, target.Y));
        target = ClampToWorkArea(target, displayIndex);

        if (displayIndex >= 0 && displayIndex < displays.Count)
        {
            appWindow.MoveAndResize(target, displays[displayIndex]);
        }
        else
        {
            appWindow.MoveAndResize(target);
        }
    }

    public static RectModel ToRectModel(RectInt32 rect)
    {
        return new RectModel { X = rect.X, Y = rect.Y, Width = rect.Width, Height = rect.Height };
    }

    /// <summary>Findet den Display-Index, auf dem ein bestimmter Punkt liegt (z. B. Mauszeiger).</summary>
    public static int FindDisplayForPoint(PointInt32 point)
    {
        var displays = GetDisplays();
        for (int i = 0; i < displays.Count; i++)
        {
            var workArea = displays[i].WorkArea;
            if (point.X >= workArea.X
                && point.Y >= workArea.Y
                && point.X < workArea.X + workArea.Width
                && point.Y < workArea.Y + workArea.Height)
            {
                return i;
            }
        }
        return 0;
    }

    /// <summary>Schiebt ein Rechteck komplett in den naechstgelegenen erreichbaren Work-Area (Fallback).</summary>
    public static RectInt32 ClampToWorkArea(RectInt32 bounds, int displayIndex)
    {
        var workArea = GetWorkArea(displayIndex);
        if (workArea.Width == 0 || workArea.Height == 0)
        {
            return bounds;
        }

        int x = bounds.X;
        int y = bounds.Y;
        int width = Math.Min(bounds.Width, workArea.Width);
        int height = Math.Min(bounds.Height, workArea.Height);

        if (x < workArea.X)
        {
            x = workArea.X;
        }
        else if (x + width > workArea.X + workArea.Width)
        {
            x = workArea.X + workArea.Width - width;
        }

        if (y < workArea.Y)
        {
            y = workArea.Y;
        }
        else if (y + height > workArea.Y + workArea.Height)
        {
            y = workArea.Y + workArea.Height - height;
        }

        return new RectInt32(x, y, width, height);
    }
}
