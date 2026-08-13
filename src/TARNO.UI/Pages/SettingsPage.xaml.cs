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
using Windows.UI;

namespace TARNO.UI.Pages;

public sealed partial class SettingsPage : Page
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

    private readonly Dictionary<string, TextBlock> _apiKeyStatusTexts = new();
    private readonly Dictionary<string, PasswordBox> _apiKeyPasswordBoxes = new();
    private bool _apiKeyRowsBuilt;
    // Verhindert einen unnoetigen Mikrofon-/Lautsprecher-Hot-Swap, wenn die
    // Combos beim Seiten-Laden nur den bereits aktiven Wert programmatisch
    // selektieren (SelectionChanged feuert sonst auch bei SelectedIndex-
    // Zuweisung aus Code, nicht nur bei echter Nutzerauswahl).
    private bool _suppressAudioDeviceEvents;

    public MainViewModel ViewModel { get; private set; } = null!;

    public SettingsPage()
    {
        this.InitializeComponent();
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
            LoadSettings();
        }
        base.OnNavigatedTo(e);
    }

    private void LoadSettings()
    {
        // ViewModel.Settings wurde bereits beim Start (MainViewModel-Konstruktor)
        // via SettingsStore.Load() aus settings.json geladen — hier nur UI spiegeln.
        SelectComboItemByTag(ThemeCombo, ViewModel.Settings.Theme);
        SelectComboItemByTag(StartupPageCombo, ViewModel.Settings.StartupPage.ToString());
        SelectComboItemByTag(LanguageCombo, ViewModel.Settings.Language);
        AutoStartSwitch.IsOn = ViewModel.Settings.AutoStart;
        AprilFoolsSwitch.IsOn = ViewModel.Settings.AprilFoolsEnabled;
        WakeWordConfirmSwitch.IsOn = ViewModel.Settings.WakeWordConfirmSound;
        SelectComboItemByTag(DictateEagernessCombo, ViewModel.Settings.DictateEagerness);
        SelectComboItemByTag(MuteHotkeyCombo, ViewModel.Settings.MuteHotkey);
        UpdateTabSelection("General");
        _ = LoadAudioDeviceCombosAsync();
    }

    /// <summary>Populiert Mikrofon-/Lautsprecher-Combos mit echten, vom
    /// Backend enumerierten Geraeten (ersetzt das angefragte, aber
    /// recherchiert-verworfene "Windows 10/11"-Konzept - siehe Plan).
    /// "Standard" ist immer die erste Option.</summary>
    private async Task LoadAudioDeviceCombosAsync()
    {
        _suppressAudioDeviceEvents = true;
        try
        {
            var mics = await ViewModel.GetMicrophoneDevicesAsync();
            MicrophoneDeviceCombo.Items.Clear();
            MicrophoneDeviceCombo.Items.Add(new ComboBoxItem { Content = "Standard", Tag = "default" });
            if (mics is not null)
            {
                foreach (var device in mics.Devices)
                {
                    string label = device.IsBuiltin ? $"{device.Name} (Eingebaut)" : device.Name;
                    MicrophoneDeviceCombo.Items.Add(new ComboBoxItem { Content = label, Tag = device.Name });
                }
            }
            SelectComboItemByTag(MicrophoneDeviceCombo, ViewModel.Settings.MicrophoneDevice);

            var speakers = await ViewModel.GetSpeakerDevicesAsync();
            SpeakerDeviceCombo.Items.Clear();
            SpeakerDeviceCombo.Items.Add(new ComboBoxItem { Content = "Standard", Tag = "default" });
            if (speakers is not null)
            {
                foreach (var device in speakers.Devices)
                {
                    string label = device.IsBuiltin ? $"{device.Name} (Eingebaut)" : device.Name;
                    SpeakerDeviceCombo.Items.Add(new ComboBoxItem { Content = label, Tag = device.Name });
                }
            }
            SelectComboItemByTag(SpeakerDeviceCombo, ViewModel.Settings.SpeakerDevice);
        }
        finally
        {
            _suppressAudioDeviceEvents = false;
        }
    }

    private void SaveSettings()
    {
        SettingsStore.Save(ViewModel.Settings);
    }

    private static void SelectComboItemByTag(ComboBox combo, string? tag)
    {
        if (string.IsNullOrWhiteSpace(tag))
        {
            combo.SelectedIndex = 0;
            return;
        }
        for (int i = 0; i < combo.Items.Count; i++)
        {
            if (combo.Items[i] is ComboBoxItem item && item.Tag is string itemTag
                && itemTag.Equals(tag, StringComparison.OrdinalIgnoreCase))
            {
                combo.SelectedIndex = i;
                return;
            }
        }
        combo.SelectedIndex = 0;
    }

    private void OnTabClick(object sender, RoutedEventArgs e)
    {
        if (sender is Button btn && btn.Tag is string tag)
        {
            InteractionLogger.Click("SettingsPage", $"Tab{tag}");
            UpdateTabSelection(tag);
        }
    }

    private void UpdateTabSelection(string selectedTag)
    {
        var primaryBrush = (SolidColorBrush)Application.Current.Resources["TextPrimaryBrush"];
        var secondaryBrush = (SolidColorBrush)Application.Current.Resources["TextSecondaryBrush"];

        void SetActive(Button button, Border indicator, bool selected)
        {
            button.Foreground = selected ? primaryBrush : secondaryBrush;
            indicator.Opacity = selected ? 1 : 0;
        }

        SetActive(TabGeneral, TabGeneralIndicator, selectedTag == "General");
        SetActive(TabVoice, TabVoiceIndicator, selectedTag == "Voice");
        SetActive(TabAi, TabAiIndicator, selectedTag == "AI");

        GeneralPanel.Visibility = selectedTag == "General" ? Visibility.Visible : Visibility.Collapsed;
        VoicePanel.Visibility = selectedTag == "Voice" ? Visibility.Visible : Visibility.Collapsed;
        AiPanel.Visibility = selectedTag == "AI" ? Visibility.Visible : Visibility.Collapsed;

        if (selectedTag == "AI")
        {
            _ = LoadApiKeyTabAsync();
        }
    }

    private async Task LoadApiKeyTabAsync()
    {
        if (!_apiKeyRowsBuilt)
        {
            BuildApiKeyRows();
            _apiKeyRowsBuilt = true;
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

        InteractionLogger.Click("SettingsPage", $"SaveApiKey_{provider}");
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

        InteractionLogger.Click("SettingsPage", $"LoginApiKey_{provider}");

        var dialog = new ProviderLoginDialog(info, passwordBox)
        {
            XamlRoot = this.XamlRoot,
        };

        await dialog.ShowAsync();

        if (!string.IsNullOrWhiteSpace(dialog.ApiKey))
        {
            statusText.Text = "Bereit zum Speichern";
            statusText.Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"];
        }
    }

    private void OnThemeChanged(object sender, SelectionChangedEventArgs e)
    {
        if (ThemeCombo.SelectedItem is ComboBoxItem item && item.Tag is string tag)
        {
            ViewModel.Settings.Theme = tag;
            InteractionLogger.Info("SETTINGS", $"Theme changed to {tag}");
        }
    }

    private void OnStartupPageChanged(object sender, SelectionChangedEventArgs e)
    {
        if (StartupPageCombo.SelectedItem is ComboBoxItem item && item.Tag is string tag
            && Enum.TryParse<AppPage>(tag, out var page))
        {
            ViewModel.Settings.StartupPage = page;
            InteractionLogger.Info("SETTINGS", $"Startup page changed to {page}");
        }
    }

    private void OnAutoStartChanged(object sender, RoutedEventArgs e)
    {
        ViewModel.Settings.AutoStart = AutoStartSwitch.IsOn;
        InteractionLogger.Info("SETTINGS", $"AutoStart changed to {AutoStartSwitch.IsOn}");
    }

    /// <summary>Zweiter Eintrittspunkt fuer denselben Sprachwechsel-Codepfad
    /// wie die Sidebar-ComboBox in MainWindow (ViewModel.SetLanguageAsync) -
    /// inkl. desselben Neustart-Hinweises, da WinUI 3 unpackaged
    /// PrimaryLanguageOverride zur Laufzeit nicht neu setzen kann.</summary>
    private async void OnLanguageChanged(object sender, SelectionChangedEventArgs e)
    {
        if (LanguageCombo.SelectedItem is not ComboBoxItem item || item.Tag is not string tag)
        {
            return;
        }
        if (ViewModel.Settings.Language == tag)
        {
            return;
        }

        InteractionLogger.Click("SettingsPage", $"LanguageChanged:{tag}");
        await ViewModel.SetLanguageAsync(tag);

        var isEn = tag == "en";
        var dialog = new ContentDialog
        {
            XamlRoot = this.XamlRoot,
            Title = isEn ? "Language changed" : "Sprache geändert",
            Content = isEn
                ? "The UI language will be applied after you restart TARNO."
                : "Die Sprache der Oberfläche wird nach einem Neustart übernommen.",
            PrimaryButtonText = "OK",
            DefaultButton = ContentDialogButton.Primary,
        };
        _ = dialog.ShowAsync();
    }

    private void OnAprilFoolsChanged(object sender, RoutedEventArgs e)
    {
        ViewModel.Settings.AprilFoolsEnabled = AprilFoolsSwitch.IsOn;
        InteractionLogger.Info("SETTINGS", $"AprilFoolsEnabled changed to {AprilFoolsSwitch.IsOn}");
    }

    private void OnWakeWordConfirmChanged(object sender, RoutedEventArgs e)
    {
        ViewModel.Settings.WakeWordConfirmSound = WakeWordConfirmSwitch.IsOn;
        InteractionLogger.Info("SETTINGS", $"WakeWordConfirmSound changed to {WakeWordConfirmSwitch.IsOn}");
    }

    private void OnDictateEagernessChanged(object sender, SelectionChangedEventArgs e)
    {
        if (DictateEagernessCombo.SelectedItem is ComboBoxItem item && item.Tag is string tag)
        {
            ViewModel.Settings.DictateEagerness = tag;
            InteractionLogger.Info("SETTINGS", $"DictateEagerness changed to {tag}");
        }
    }

    private void OnMuteHotkeyChanged(object sender, SelectionChangedEventArgs e)
    {
        if (MuteHotkeyCombo.SelectedItem is ComboBoxItem item && item.Tag is string tag)
        {
            ViewModel.Settings.MuteHotkey = tag;
            InteractionLogger.Info("SETTINGS", $"MuteHotkey changed to {tag}");
        }
    }

    private async void OnMicrophoneDeviceChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_suppressAudioDeviceEvents) return;
        if (MicrophoneDeviceCombo.SelectedItem is ComboBoxItem item && item.Tag is string tag)
        {
            ViewModel.Settings.MicrophoneDevice = tag;
            InteractionLogger.Info("SETTINGS", $"MicrophoneDevice changed to {tag}");
            await ViewModel.SetMicrophoneDeviceAsync(tag);
        }
    }

    private async void OnSpeakerDeviceChanged(object sender, SelectionChangedEventArgs e)
    {
        if (_suppressAudioDeviceEvents) return;
        if (SpeakerDeviceCombo.SelectedItem is ComboBoxItem item && item.Tag is string tag)
        {
            ViewModel.Settings.SpeakerDevice = tag;
            InteractionLogger.Info("SETTINGS", $"SpeakerDevice changed to {tag}");
            await ViewModel.SetSpeakerDeviceAsync(tag);
        }
    }

    private void OnSaveSettingsClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("SettingsPage", "SaveSettings");
        SaveSettings();
        (Application.Current as App)?.ReloadMuteHotkey();
    }
}
