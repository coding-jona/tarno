using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Shapes;
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace TARNO.UI.Dialogs;

/// <summary>
/// First-Start-Wizard: fragt beim allerersten Programmstart nach mindestens
/// einem LLM-Provider-API-Key, falls noch keiner im SecretsVault konfiguriert ist.
/// Schreibt direkt über MainViewModel.SetApiKeyAsync in den Vault (gRPC -> SecretsVault).
/// </summary>
public sealed partial class FirstStartWizardDialog : ContentDialog
{
    private static readonly (string Provider, string Label)[] ApiKeyProviders = new[]
    {
        ("mistral", "Mistral"),
        ("openai", "OpenAI"),
        ("gemini", "Gemini"),
        ("groq", "Groq"),
        ("huggingface", "Hugging Face"),
        ("claude", "Claude (Anthropic)"),
    };

    private readonly MainViewModel _viewModel;
    private readonly Dictionary<string, PasswordBox> _passwordBoxes = new();

    public FirstStartWizardDialog(MainViewModel viewModel)
    {
        _viewModel = viewModel;
        this.InitializeComponent();
        BuildApiKeyRows();
    }

    private void BuildApiKeyRows()
    {
        for (int i = 0; i < ApiKeyProviders.Length; i++)
        {
            var (provider, label) = ApiKeyProviders[i];

            var row = new StackPanel { Spacing = 6 };
            row.Children.Add(new TextBlock
            {
                Text = label,
                FontSize = 13,
                Foreground = (SolidColorBrush)Application.Current.Resources["TextPrimaryBrush"],
            });

            var inputGrid = new Grid { ColumnSpacing = 8 };
            inputGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            inputGrid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var passwordBox = new PasswordBox
            {
                PlaceholderText = "API-Key eingeben (optional)...",
                Style = (Style)Application.Current.Resources["GlassPasswordBoxStyle"],
            };
            _passwordBoxes[provider] = passwordBox;
            Grid.SetColumn(passwordBox, 0);
            inputGrid.Children.Add(passwordBox);

            var loginButton = new Button
            {
                Content = "Holen",
                Style = (Style)Application.Current.Resources["GlassSecondaryButtonStyle"],
                VerticalAlignment = VerticalAlignment.Center,
            };
            loginButton.Click += async (_, _) => await OnLoginApiKeyClick(provider, passwordBox);
            ToolTipService.SetToolTip(loginButton, "API-Key über Provider-Login abrufen");
            Grid.SetColumn(loginButton, 1);
            inputGrid.Children.Add(loginButton);

            row.Children.Add(inputGrid);

            ApiKeyRowsPanel.Children.Add(row);

            if (i < ApiKeyProviders.Length - 1)
            {
                ApiKeyRowsPanel.Children.Add(new Rectangle
                {
                    Height = 1,
                    Fill = (SolidColorBrush)Application.Current.Resources["DividerBrush"],
                });
            }
        }
    }

    private async void OnPrimaryButtonClick(ContentDialog sender, ContentDialogButtonClickEventArgs args)
    {
        var deferral = args.GetDeferral();
        try
        {
            if (LanguageCombo.SelectedItem is ComboBoxItem item && item.Tag is string language)
            {
                await _viewModel.SetLanguageAsync(language);
            }

            var failures = new List<string>();
            foreach (var (provider, passwordBox) in EnumerateFilledBoxes())
            {
                var (success, message) = await _viewModel.SetApiKeyAsync(provider, passwordBox.Password);
                if (!success)
                {
                    failures.Add($"{provider}: {message}");
                }
            }

            if (failures.Count > 0)
            {
                // Nicht schliessen - der Nutzer soll nicht glauben, ein Key sei
                // gespeichert, wenn das Backend/der Vault ihn abgelehnt hat.
                args.Cancel = true;
                ErrorText.Text = "Konnte nicht gespeichert werden: " + string.Join("; ", failures);
                ErrorText.Visibility = Visibility.Visible;
            }
        }
        catch (Exception ex)
        {
            // async void ContentDialog event: an uncaught exception here
            // would crash the whole app instead of just failing the wizard.
            InteractionLogger.Error("FIRSTSTART", $"Key-Speicherung fehlgeschlagen: {ex.Message}");
            args.Cancel = true;
            ErrorText.Text = "Unerwarteter Fehler: " + ex.Message;
            ErrorText.Visibility = Visibility.Visible;
        }
        finally
        {
            deferral.Complete();
        }
    }

    private async Task OnLoginApiKeyClick(string provider, PasswordBox passwordBox)
    {
        var info = ProviderOnboardingService.Get(provider);
        if (info is null)
        {
            return;
        }

        InteractionLogger.Click("FirstStartWizard", $"LoginApiKey_{provider}");

        var dialog = new ProviderLoginDialog(info, passwordBox)
        {
            XamlRoot = this.XamlRoot,
        };

        await dialog.ShowAsync();
    }

    private void OnSecondaryButtonClick(ContentDialog sender, ContentDialogButtonClickEventArgs args)
    {
        // "Später konfigurieren" - Dialog schließt ohne zu speichern.
    }

    private IEnumerable<(string Provider, PasswordBox Box)> EnumerateFilledBoxes()
    {
        foreach (var (provider, box) in _passwordBoxes)
        {
            if (!string.IsNullOrWhiteSpace(box.Password))
            {
                yield return (provider, box);
            }
        }
    }
}
