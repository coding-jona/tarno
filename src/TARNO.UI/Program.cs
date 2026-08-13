using System;
using System.Linq;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Windows.Globalization;

namespace TARNO.UI;

/// <summary>
/// Custom application entry point. Required so we can set
/// ApplicationLanguages.PrimaryLanguageOverride *before* Application.Start,
/// which fixes the WinUI 3 unpackaged InvalidOperationException thrown when
/// the property is accessed after resources are loaded.
/// </summary>
internal static class Program
{
    private static readonly string[] AprilFoolsFlags = { "--april-fools", "--aprilfools", "-april" };

    [STAThread]
    private static void Main(string[] args)
    {
        try
        {
            var settings = SettingsStore.Load();
            ApplicationLanguages.PrimaryLanguageOverride =
                settings.Language == "en" ? "en-US" : "de-DE";

            if (args.Any(a => AprilFoolsFlags.Contains(a, StringComparer.OrdinalIgnoreCase)))
            {
                AprilFoolsConfigService.CommandLineOverride = true;
            }
        }
        catch (Exception ex)
        {
            // If settings cannot be loaded, fall back to the system default.
            System.Diagnostics.Debug.WriteLine($"Could not set language override: {ex.Message}");
        }

        WinRT.ComWrappersSupport.InitializeComWrappers();
        Application.Start(_ =>
        {
            var context = new DispatcherQueueSynchronizationContext(DispatcherQueue.GetForCurrentThread());
            System.Threading.SynchronizationContext.SetSynchronizationContext(context);
            new App();
        });
    }
}
