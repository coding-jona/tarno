using System;
using System.Text.RegularExpressions;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using TARNO.UI.Models;
using Windows.ApplicationModel.DataTransfer;

namespace TARNO.UI.Dialogs;

public sealed partial class ProviderLoginDialog : ContentDialog
{
    private readonly ProviderOnboardingInfo _info;
    private readonly PasswordBox? _targetPasswordBox;

    public string? ApiKey { get; private set; }

    public ProviderLoginDialog(ProviderOnboardingInfo info, PasswordBox? targetPasswordBox = null)
    {
        _info = info;
        _targetPasswordBox = targetPasswordBox;
        this.InitializeComponent();
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        InstructionsText.Text = _info.Instructions;
        StatusText.Text = "Lade Provider-Seite...";
        ErrorText.Visibility = Visibility.Collapsed;

        try
        {
            var uri = new Uri(_info.DashboardUrl, UriKind.Absolute);
            ProviderWebView.Source = uri;
        }
        catch (Exception ex)
        {
            ShowError($"WebView konnte nicht geladen werden: {ex.Message}");
        }

        ProviderWebView.NavigationStarting += (_, args) =>
        {
            StatusText.Text = $"Navigiere zu: {args.Uri ?? "-"}";
        };

        ProviderWebView.NavigationCompleted += (_, args) =>
        {
            StatusText.Text = args.IsSuccess
                ? $"Bereit: {ProviderWebView.Source?.ToString() ?? "-"}"
                : "Seite konnte nicht vollständig geladen werden.";
        };
    }

    private async void OnPasteFromClipboardClick(object sender, RoutedEventArgs e)
    {
        ErrorText.Visibility = Visibility.Collapsed;

        try
        {
            var dataPackageView = Clipboard.GetContent();
            if (!dataPackageView.Contains(StandardDataFormats.Text))
            {
                ShowError("Zwischenablage enthält keinen Text.");
                return;
            }

            string text = await dataPackageView.GetTextAsync();
            if (string.IsNullOrWhiteSpace(text))
            {
                ShowError("Zwischenablage ist leer.");
                return;
            }

            string key = text.Trim();
            if (_info.KeyRegex is Regex regex && !regex.IsMatch(key))
            {
                ShowError("Der eingefügte Text sieht nicht wie ein gültiger API-Key für diesen Provider aus.");
                return;
            }

            ApiKey = key;
            if (_targetPasswordBox is not null)
            {
                _targetPasswordBox.Password = key;
            }
            Hide();
        }
        catch (Exception ex)
        {
            ShowError($"Fehler beim Lesen der Zwischenablage: {ex.Message}");
        }
    }

    private void OnManualClick(object sender, RoutedEventArgs e)
    {
        // Schließt den Dialog ohne Key, damit der Nutzer ihn selbst eintippen kann.
        ApiKey = null;
        Hide();
    }

    private void ShowError(string message)
    {
        ErrorText.Text = message;
        ErrorText.Visibility = Visibility.Visible;
    }
}
