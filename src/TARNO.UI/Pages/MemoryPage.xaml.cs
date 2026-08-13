using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Navigation;
using System;
using Windows.Storage;
using Windows.Storage.Pickers;

namespace TARNO.UI.Pages;

public sealed partial class MemoryPage : Page
{
    public MainViewModel ViewModel { get; private set; } = null!;

    public MemoryPage()
    {
        this.InitializeComponent();
    }

    protected override async void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
            Bindings.Update();
            try
            {
                await ViewModel.LoadMemoryAsync();
            }
            catch (Exception ex)
            {
                InteractionLogger.Error("MEMORY", $"Gedächtnis konnte nicht geladen werden: {ex.Message}");
            }
        }
        base.OnNavigatedTo(e);
    }

    private async void OnSearchKeyDown(object sender, KeyRoutedEventArgs e)
    {
        if (e.Key != Windows.System.VirtualKey.Enter || sender is not TextBox textBox)
        {
            return;
        }
        try
        {
            await ViewModel.LoadMemoryAsync(textBox.Text.Trim());
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("MEMORY", $"Gedächtnis-Suche fehlgeschlagen: {ex.Message}");
        }
    }

    private async void OnImportClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MemoryPage", "Import");
        try
        {
            var picker = new FileOpenPicker();
            var hwnd = WinRT.Interop.WindowNative.GetWindowHandle(App.MainWindow);
            WinRT.Interop.InitializeWithWindow.Initialize(picker, hwnd);
            picker.FileTypeFilter.Add(".json");

            StorageFile? file = await picker.PickSingleFileAsync();
            if (file is null)
            {
                return;
            }

            var jsonText = await FileIO.ReadTextAsync(file);
            var (success, count, message) = await ViewModel.ImportMemoryAsync(jsonText);
            if (!success)
            {
                InteractionLogger.Error("MEMORY", $"Import fehlgeschlagen: {message}");
            }
            else
            {
                InteractionLogger.Info("MEMORY", $"Import erfolgreich: {count} Einträge.");
            }
        }
        catch (Exception ex)
        {
            InteractionLogger.Error("MEMORY", $"Import fehlgeschlagen: {ex.Message}");
        }
    }
}
