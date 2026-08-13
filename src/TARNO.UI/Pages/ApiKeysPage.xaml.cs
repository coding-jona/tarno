using TARNO.UI.Dialogs;
using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Navigation;
using Microsoft.UI.Xaml.Shapes;
using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace TARNO.UI.Pages;

/// <summary>
/// Zentrale API-Keys-Seite: deckt alle Provider ab, die tatsaechlich einen
/// Key benoetigen (Ollama laeuft lokal, braucht keinen - siehe
/// tarno/ai/factory.py provider_has_api_key). Eigener Navigationspunkt,
/// bewusst getrennt von SettingsPage (dessen "KI"-Tab weiterhin die
/// urspruenglichen 6 Provider zeigt und unangetastet bleibt) - wichtig,
/// seit der Agent-Pool mehrere Provider gleichzeitig nutzen kann und der
/// Nutzer dafuer schnell alle Keys an einem Ort einrichten koennen soll.
/// Wiederverwendet SetApiKeyAsync/GetApiKeyStatusAsync unveraendert.
/// </summary>
public sealed partial class ApiKeysPage : Page
{
    private static readonly (string Provider, string Label)[] ApiKeyProviders = new[]
    {
        ("mistral", "Mistral"),
        ("claude", "Claude (Anthropic)"),
        ("gemini", "Gemini"),
        ("groq", "Groq"),
        ("huggingface", "Hugging Face"),
        ("openai", "OpenAI"),
        ("glm", "GLM"),
        ("perplexity", "Perplexity"),
        ("meta", "Meta"),
        ("deepseek", "DeepSeek"),
        ("moonshot", "Moonshot (Kimi)"),
        ("qwen", "Qwen"),
        ("openrouter", "OpenRouter"),
    };

    private readonly Dictionary<string, TextBlock> _apiKeyStatusTexts = new();
    private readonly Dictionary<string, PasswordBox> _apiKeyPasswordBoxes = new();
    private bool _rowsBuilt;

    public MainViewModel ViewModel { get; private set; } = null!;

    public ApiKeysPage()
    {
        this.InitializeComponent();
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
            _ = LoadApiKeysAsync();
        }
        base.OnNavigatedTo(e);
    }

    private async Task LoadApiKeysAsync()
    {
        if (!_rowsBuilt)
        {
            BuildApiKeyRows();
            _rowsBuilt = true;
        }

        Dictionary<string, bool> status;
        try
        {
            status = await ViewModel.GetApiKeyStatusAsync();
        }
        catch (Exception)
        {
            return;
        }

        foreach (var (provider, _) in ApiKeyProviders)
        {
            if (!_apiKeyStatusTexts.TryGetValue(provider, out var statusText))
            {
                continue;
            }
            bool configured = status.TryGetValue(provider, out var value) && value;
            statusText.Text = configured ? "Konfiguriert" : "Nicht konfiguriert";
            statusText.Foreground = configured
                ? (SolidColorBrush)Application.Current.Resources["SuccessBrush"]
                : (SolidColorBrush)Application.Current.Resources["TextMutedBrush"];
        }
    }

    private void BuildApiKeyRows()
    {
        ApiKeyRowsPanel.Children.Clear();
        _apiKeyStatusTexts.Clear();
        _apiKeyPasswordBoxes.Clear();

        for (int i = 0; i < ApiKeyProviders.Length; i++)
        {
            var (provider, label) = ApiKeyProviders[i];

            var row = new Grid { ColumnSpacing = 12 };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(140) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var labelStack = new StackPanel { Spacing = 2, VerticalAlignment = VerticalAlignment.Center };
            labelStack.Children.Add(new TextBlock
            {
                Text = label,
                FontSize = 14,
                Foreground = (SolidColorBrush)Application.Current.Resources["TextPrimaryBrush"],
            });
            var statusText = new TextBlock
            {
                Text = "…",
                FontSize = 11,
                Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"],
            };
            labelStack.Children.Add(statusText);
            _apiKeyStatusTexts[provider] = statusText;
            Grid.SetColumn(labelStack, 0);
            row.Children.Add(labelStack);

            var passwordBox = new PasswordBox
            {
                PlaceholderText = "API-Key eingeben...",
                Style = (Style)Application.Current.Resources["GlassPasswordBoxStyle"],
                VerticalAlignment = VerticalAlignment.Center,
            };
            _apiKeyPasswordBoxes[provider] = passwordBox;
            Grid.SetColumn(passwordBox, 1);
            row.Children.Add(passwordBox);

            var saveButton = new Button
            {
                Content = "Speichern",
                Style = (Style)Application.Current.Resources["GlassSecondaryButtonStyle"],
                VerticalAlignment = VerticalAlignment.Center,
            };
            saveButton.Click += async (_, _) => await OnSaveApiKeyClick(provider, passwordBox, statusText, saveButton);
            Grid.SetColumn(saveButton, 2);
            row.Children.Add(saveButton);

            var loginButton = new Button
            {
                Content = "Holen",
                Style = (Style)Application.Current.Resources["GlassSecondaryButtonStyle"],
                VerticalAlignment = VerticalAlignment.Center,
                Margin = new Thickness(8, 0, 0, 0),
            };
            loginButton.Click += async (_, _) => await OnLoginApiKeyClick(provider, passwordBox, statusText);
            ToolTipService.SetToolTip(loginButton, "API-Key über Provider-Login abrufen");
            Grid.SetColumn(loginButton, 3);
            row.Children.Add(loginButton);

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

    private async Task OnSaveApiKeyClick(string provider, PasswordBox passwordBox, TextBlock statusText, Button saveButton)
    {
        string key = passwordBox.Password;
        if (string.IsNullOrWhiteSpace(key))
        {
            return;
        }

        InteractionLogger.Click("ApiKeysPage", $"SaveApiKey_{provider}");
        saveButton.IsEnabled = false;
        try
        {
            var (success, message) = await ViewModel.SetApiKeyAsync(provider, key);
            if (success)
            {
                passwordBox.Password = string.Empty;
                statusText.Text = "Konfiguriert";
                statusText.Foreground = (SolidColorBrush)Application.Current.Resources["SuccessBrush"];
            }
            else
            {
                statusText.Text = message;
                statusText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
            }
        }
        finally
        {
            saveButton.IsEnabled = true;
        }
    }

    private async Task OnLoginApiKeyClick(string provider, PasswordBox passwordBox, TextBlock statusText)
    {
        var info = ProviderOnboardingService.Get(provider);
        if (info is null)
        {
            statusText.Text = "Keine Onboarding-Daten für diesen Provider.";
            statusText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
            return;
        }

        InteractionLogger.Click("ApiKeysPage", $"LoginApiKey_{provider}");

        var dialog = new ProviderLoginDialog(info, passwordBox)
        {
            XamlRoot = this.XamlRoot,
        };

        await dialog.ShowAsync();
    }
}
