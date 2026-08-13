using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Media;
using System;
using Windows.UI;

namespace TARNO.UI.Converters;

/// <summary>
/// Static x:Bind helpers. Inside a Window, x:Bind cannot use
/// Converter={StaticResource ...} (needs a FrameworkElement root),
/// so the sidebar binds through this function instead.
/// </summary>
public static class Nav
{
    public static bool IsPage(AppPage current, string name)
        => string.Equals(current.ToString(), name, StringComparison.OrdinalIgnoreCase);
}

public sealed class EnumToBoolConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        if (value == null || parameter == null)
        {
            return false;
        }

        var valueString = value.ToString();
        var parameterString = parameter.ToString();
        return string.Equals(valueString, parameterString, StringComparison.OrdinalIgnoreCase);
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

public sealed class RoleToBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        var role = value?.ToString() ?? string.Empty;
        // Dezente, transluzente Boxen statt massiver Cyan-Fläche (Lead-UX-
        // Briefing 2026-07-14) — beide Rollen erben die Glas-Card-Tokens,
        // die Rolle unterscheidet sich nur über den Rand (siehe
        // RoleToBorderBrushConverter).
        return role.Equals("user", StringComparison.OrdinalIgnoreCase)
            ? Application.Current.Resources["UserBubbleBackgroundBrush"]
            : Application.Current.Resources["GlassCardBackgroundBrush"];
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

public sealed class RoleToBorderBrushConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        var role = value?.ToString() ?? string.Empty;
        return role.Equals("user", StringComparison.OrdinalIgnoreCase)
            ? Application.Current.Resources["UserBubbleBorderBrush"]
            : Application.Current.Resources["GlassCardBorderBrush"];
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}

public sealed class RoleToAlignmentConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, string language)
    {
        var role = value?.ToString() ?? string.Empty;
        return role.Equals("user", StringComparison.OrdinalIgnoreCase)
            ? HorizontalAlignment.Right
            : HorizontalAlignment.Left;
    }

    public object ConvertBack(object value, Type targetType, object parameter, string language)
    {
        throw new NotImplementedException();
    }
}
