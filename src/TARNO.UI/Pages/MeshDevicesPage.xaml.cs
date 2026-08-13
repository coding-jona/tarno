using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Dispatching;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Microsoft.UI.Xaml.Navigation;
using System;
using System.Linq;
using System.Runtime.InteropServices.WindowsRuntime;
using System.Text.Json;
using System.Threading.Tasks;
using Windows.Storage.Streams;

namespace TARNO.UI.Pages;

/// <summary>
/// Geräte-Verwaltung fürs Dynamic Hybrid Mesh: Login (inkl. optionalem
/// TOTP-2FA) + Passwort-Reset gegen den Tarno-Server (eigener REST-Dienst,
/// siehe tarno-server/README.md im Repo-Root - läuft unabhängig vom
/// bestehenden gRPC-Kanal zum Python-Backend, ändert also nichts an dessen
/// Vertrag), Geräteliste mit Online-Status (aus last_seen_at abgeleitet),
/// Geräte-Registrierung, 2FA-Verwaltung (Einrichten/Deaktivieren).
///
/// Erste Seite der "Schaltzentrale" - bewusst zuerst die Verbindungsseite
/// (Login + Geräte-Übersicht), Dashboards/Detailseiten folgen später.
/// </summary>
public sealed partial class MeshDevicesPage : Page
{
    // Ein Gerät gilt als "online", wenn sein letzter Sync nicht länger als
    // dieses Fenster zurückliegt. Größer als der ESP32-Cloud-Sync-Intervall
    // (30s, siehe esp32-mesh-node/main/Kconfig.projbuild) plus Puffer für
    // Netzwerk-Jitter, damit es nicht staendig zwischen online/offline flackert.
    private static readonly TimeSpan OnlineThreshold = TimeSpan.FromSeconds(90);
    private static readonly TimeSpan AutoRefreshInterval = TimeSpan.FromSeconds(15);

    public MainViewModel ViewModel { get; private set; } = null!;

    private MeshServerClient? _client;
    private string? _accessToken;
    private DispatcherTimer? _refreshTimer;

    // Zwischenspeicher fuer den zweistufigen 2FA-Login: nach LoginAsync mit
    // RequiresTwoFactor=true wird hier der PendingToken + die eingegebene
    // E-Mail gehalten, bis der Code bestaetigt wird.
    private string? _pendingTwoFactorToken;
    private string? _pendingLoginEmail;

    public MeshDevicesPage()
    {
        this.InitializeComponent();
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
            ServerUrlDisplayText.Text = ViewModel.Settings.MeshServerUrl;
            _client = new MeshServerClient(ViewModel.Settings.MeshServerUrl);

            var saved = MeshCredentialStore.LoadToken();
            if (saved is { } token)
            {
                _accessToken = token.AccessToken;
                AccountEmailText.Text = $"Angemeldet als {token.Email}";
                ShowLoggedInState();
                _ = RefreshDevicesAsync();
                _ = RefreshTwoFactorStatusAsync();
            }
            else
            {
                ShowLoggedOutState();
            }

            StartAutoRefresh();
        }
        base.OnNavigatedTo(e);
    }

    protected override void OnNavigatedFrom(NavigationEventArgs e)
    {
        StopAutoRefresh();
        _client?.Dispose();
        _client = null;
        base.OnNavigatedFrom(e);
    }

    private void StartAutoRefresh()
    {
        StopAutoRefresh();
        _refreshTimer = new DispatcherTimer { Interval = AutoRefreshInterval };
        _refreshTimer.Tick += async (_, _) =>
        {
            if (_accessToken is not null)
            {
                await RefreshDevicesAsync();
            }
        };
        _refreshTimer.Start();
    }

    private void StopAutoRefresh()
    {
        _refreshTimer?.Stop();
        _refreshTimer = null;
    }

    // OnSaveServerUrlClick entfernt (KERNFIX): die Server-URL wird nicht mehr
    // per App geaendert, siehe Kommentar in MeshDevicesPage.xaml bei
    // ServerUrlDisplayText. Ein Server-Wechsel erfordert jetzt einen Neustart
    // der App, nachdem settings.json manuell bearbeitet wurde - bewusste
    // Reibung fuer eine sicherheitsrelevante Einstellung.

    // ---- Login / 2FA-Bestaetigung / Registrierung ----

    private async Task OnLoginClick_Async()
    {
        string email = EmailTextBox.Text.Trim();
        string password = PasswordBox.Password;
        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password) || _client is null)
        {
            return;
        }

        LoginButton.IsEnabled = false;
        LoginStatusText.Text = "Melde an...";
        LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"];
        try
        {
            var result = await _client.LoginAsync(email, password);
            if (!result.Success)
            {
                LoginStatusText.Text = result.Error ?? "Login fehlgeschlagen.";
                LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                return;
            }

            if (result.RequiresTwoFactor)
            {
                _pendingTwoFactorToken = result.PendingToken;
                _pendingLoginEmail = email;
                LoginCredentialsPanel.Visibility = Visibility.Collapsed;
                LoginTwoFactorPanel.Visibility = Visibility.Visible;
                LoginStatusText.Text = "Passwort korrekt - jetzt den 2FA-Code eingeben.";
                LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"];
                return;
            }

            if (result.AccessToken is null)
            {
                LoginStatusText.Text = "Unerwartete Server-Antwort ohne Token.";
                LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                return;
            }

            await CompleteLoginAsync(email, result.AccessToken);
        }
        finally
        {
            LoginButton.IsEnabled = true;
        }
    }

    private void OnLoginClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "Login");
        _ = OnLoginClick_Async();
    }

    private async Task OnLoginTwoFactorConfirmClick_Async()
    {
        string code = LoginTwoFactorCodeBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(code) || _client is null || _pendingTwoFactorToken is null || _pendingLoginEmail is null)
        {
            return;
        }

        LoginTwoFactorConfirmButton.IsEnabled = false;
        try
        {
            var result = await _client.VerifyTwoFactorAsync(_pendingTwoFactorToken, code);
            if (!result.Success || result.AccessToken is null)
            {
                LoginStatusText.Text = result.Error ?? "Code falsch.";
                LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                return;
            }

            string email = _pendingLoginEmail;
            LoginTwoFactorCodeBox.Text = string.Empty;
            await CompleteLoginAsync(email, result.AccessToken);
        }
        finally
        {
            LoginTwoFactorConfirmButton.IsEnabled = true;
        }
    }

    private void OnLoginTwoFactorConfirmClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "LoginTwoFactorConfirm");
        _ = OnLoginTwoFactorConfirmClick_Async();
    }

    private void OnLoginTwoFactorCancelClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "LoginTwoFactorCancel");
        _pendingTwoFactorToken = null;
        _pendingLoginEmail = null;
        LoginTwoFactorCodeBox.Text = string.Empty;
        LoginTwoFactorPanel.Visibility = Visibility.Collapsed;
        LoginCredentialsPanel.Visibility = Visibility.Visible;
        LoginStatusText.Text = string.Empty;
    }

    private async Task CompleteLoginAsync(string email, string accessToken)
    {
        _accessToken = accessToken;
        _pendingTwoFactorToken = null;
        _pendingLoginEmail = null;
        MeshCredentialStore.SaveToken(email, accessToken);
        AccountEmailText.Text = $"Angemeldet als {email}";
        PasswordBox.Password = string.Empty;
        ShowLoggedInState();
        await RefreshDevicesAsync();
        await RefreshTwoFactorStatusAsync();
    }

    private async Task OnRegisterClick_Async()
    {
        string email = EmailTextBox.Text.Trim();
        string password = PasswordBox.Password;
        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(password) || _client is null)
        {
            return;
        }

        RegisterButton.IsEnabled = false;
        LoginStatusText.Text = "Registriere...";
        LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"];
        try
        {
            var result = await _client.RegisterAsync(email, password);
            if (!result.Success)
            {
                LoginStatusText.Text = result.Error ?? "Registrierung fehlgeschlagen.";
                LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                return;
            }

            LoginStatusText.Text = "Registriert - jetzt einloggen.";
            LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["SuccessBrush"];
        }
        finally
        {
            RegisterButton.IsEnabled = true;
        }
    }

    private void OnRegisterClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "Register");
        _ = OnRegisterClick_Async();
    }

    // ---- Passwort-Reset ----

    private void OnForgotPasswordLinkClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "ForgotPasswordLink");
        ResetEmailTextBox.Text = EmailTextBox.Text;
        LoginCredentialsPanel.Visibility = Visibility.Collapsed;
        PasswordResetPanel.Visibility = Visibility.Visible;
        LoginStatusText.Text = string.Empty;
    }

    private void OnResetPasswordCancelClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "ResetPasswordCancel");
        PasswordResetPanel.Visibility = Visibility.Collapsed;
        LoginCredentialsPanel.Visibility = Visibility.Visible;
        ResetCodeTextBox.Text = string.Empty;
        ResetNewPasswordBox.Password = string.Empty;
    }

    private async Task OnResetPasswordClick_Async()
    {
        string email = ResetEmailTextBox.Text.Trim();
        string code = ResetCodeTextBox.Text.Trim();
        string newPassword = ResetNewPasswordBox.Password;
        if (string.IsNullOrWhiteSpace(email) || string.IsNullOrWhiteSpace(code) || string.IsNullOrWhiteSpace(newPassword) || _client is null)
        {
            return;
        }

        ResetPasswordButton.IsEnabled = false;
        try
        {
            var result = await _client.ResetPasswordAsync(email, code, newPassword);
            if (!result.Success)
            {
                LoginStatusText.Text = result.Error ?? "Zurücksetzen fehlgeschlagen.";
                LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                return;
            }

            ResetCodeTextBox.Text = string.Empty;
            ResetNewPasswordBox.Password = string.Empty;
            PasswordResetPanel.Visibility = Visibility.Collapsed;
            LoginCredentialsPanel.Visibility = Visibility.Visible;
            EmailTextBox.Text = email;
            LoginStatusText.Text = "Passwort geändert - jetzt einloggen.";
            LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["SuccessBrush"];
        }
        finally
        {
            ResetPasswordButton.IsEnabled = true;
        }
    }

    private void OnResetPasswordClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "ResetPassword");
        _ = OnResetPasswordClick_Async();
    }

    // ---- Account ----

    private void OnLogoutClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "Logout");
        _accessToken = null;
        MeshCredentialStore.Clear();
        DeviceRowsPanel.Children.Clear();
        ShowLoggedOutState();
    }

    private void OnRefreshClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "Refresh");
        _ = RefreshDevicesAsync();
    }

    private async Task RefreshDevicesAsync()
    {
        if (_client is null || _accessToken is null)
        {
            return;
        }

        var result = await _client.ListDevicesAsync(_accessToken);
        if (!result.Success)
        {
            if (result.IsUnauthorized)
            {
                // Token wirklich ungueltig (HTTP 401) - sauber zurueck zum
                // Login statt eine tote Geraeteliste zu zeigen.
                _accessToken = null;
                MeshCredentialStore.Clear();
                ShowLoggedOutState();
                LoginStatusText.Text = result.Error;
                LoginStatusText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
            }
            // KERNFIX: sonst (Netzwerkfehler, Server kurz down) NICHT
            // ausloggen - der Token ist vermutlich noch gueltig, der naechste
            // Auto-Refresh-Tick versucht es einfach erneut. Vorher wurde hier
            // bedingungslos MeshCredentialStore.Clear() aufgerufen, was einen
            // kurzen Verbindungsaussetzer (z.B. Tunnel-Neustart) in einen
            // dauerhaften Logout verwandelte.
            return;
        }

        BuildDeviceRows(result.Devices);
    }

    // ---- 2FA-Verwaltung ----

    private async Task RefreshTwoFactorStatusAsync()
    {
        if (_client is null || _accessToken is null)
        {
            return;
        }

        var result = await _client.GetMeAsync(_accessToken);
        if (!result.Success)
        {
            return; // RefreshDevicesAsync faengt abgelaufene Tokens bereits ab
        }

        SetTwoFactorEnabledUi(result.TotpEnabled);
    }

    private void SetTwoFactorEnabledUi(bool enabled)
    {
        TwoFactorStatusText.Text = enabled ? "An" : "Aus";
        TwoFactorStatusText.Foreground = (SolidColorBrush)Application.Current.Resources[enabled ? "SuccessBrush" : "TextMutedBrush"];
        StartTwoFactorSetupButton.Visibility = enabled ? Visibility.Collapsed : Visibility.Visible;
        TwoFactorDisablePanel.Visibility = enabled ? Visibility.Visible : Visibility.Collapsed;
        if (!enabled)
        {
            // Nur zuruecksetzen, wenn wir NICHT gerade mitten im
            // Setup-Bestaetigungs-Flow sind (sonst wuerde das QR-Panel direkt
            // nach dem ersten SetupTwoFactorAsync-Aufruf wieder verschwinden,
            // weil der Account zu dem Zeitpunkt ja noch totp_enabled=false ist).
            TwoFactorDisableCodeBox.Text = string.Empty;
        }
    }

    private async Task OnStartTwoFactorSetupClick_Async()
    {
        if (_client is null || _accessToken is null)
        {
            return;
        }

        StartTwoFactorSetupButton.IsEnabled = false;
        TwoFactorStatusMessageText.Text = "Secret wird erzeugt...";
        TwoFactorStatusMessageText.Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"];
        try
        {
            var result = await _client.SetupTwoFactorAsync(_accessToken);
            if (!result.Success || result.Secret is null || result.QrCodeBase64Png is null)
            {
                TwoFactorStatusMessageText.Text = result.Error ?? "Setup fehlgeschlagen.";
                TwoFactorStatusMessageText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                return;
            }

            TwoFactorSecretText.Text = $"Secret (manuell eintragbar): {result.Secret}";
            await SetQrImageAsync(result.QrCodeBase64Png);
            StartTwoFactorSetupButton.Visibility = Visibility.Collapsed;
            TwoFactorSetupPanel.Visibility = Visibility.Visible;
            TwoFactorStatusMessageText.Text = string.Empty;
        }
        finally
        {
            StartTwoFactorSetupButton.IsEnabled = true;
        }
    }

    private void OnStartTwoFactorSetupClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "StartTwoFactorSetup");
        _ = OnStartTwoFactorSetupClick_Async();
    }

    private async Task SetQrImageAsync(string base64Png)
    {
        byte[] bytes = Convert.FromBase64String(base64Png);
        using var stream = new InMemoryRandomAccessStream();
        await stream.WriteAsync(bytes.AsBuffer());
        stream.Seek(0);

        var bitmap = new BitmapImage();
        await bitmap.SetSourceAsync(stream);
        TwoFactorQrImage.Source = bitmap;
    }

    private async Task OnConfirmTwoFactorEnableClick_Async()
    {
        string code = TwoFactorEnableCodeBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(code) || _client is null || _accessToken is null)
        {
            return;
        }

        ConfirmTwoFactorEnableButton.IsEnabled = false;
        try
        {
            var result = await _client.EnableTwoFactorAsync(_accessToken, code);
            if (!result.Success)
            {
                TwoFactorStatusMessageText.Text = result.Error ?? "Code falsch.";
                TwoFactorStatusMessageText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                return;
            }

            TwoFactorEnableCodeBox.Text = string.Empty;
            TwoFactorSetupPanel.Visibility = Visibility.Collapsed;
            BackupCodesText.Text = string.Join("   ", result.BackupCodes);
            BackupCodesPanel.Visibility = Visibility.Visible;
            SetTwoFactorEnabledUi(true);
        }
        finally
        {
            ConfirmTwoFactorEnableButton.IsEnabled = true;
        }
    }

    private void OnConfirmTwoFactorEnableClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "ConfirmTwoFactorEnable");
        _ = OnConfirmTwoFactorEnableClick_Async();
    }

    private async Task OnDisableTwoFactorClick_Async()
    {
        string code = TwoFactorDisableCodeBox.Text.Trim();
        if (string.IsNullOrWhiteSpace(code) || _client is null || _accessToken is null)
        {
            return;
        }

        DisableTwoFactorButton.IsEnabled = false;
        try
        {
            var result = await _client.DisableTwoFactorAsync(_accessToken, code);
            if (!result.Success)
            {
                TwoFactorStatusMessageText.Text = result.Error ?? "Code falsch.";
                TwoFactorStatusMessageText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                return;
            }

            BackupCodesPanel.Visibility = Visibility.Collapsed;
            TwoFactorStatusMessageText.Text = "2FA deaktiviert.";
            TwoFactorStatusMessageText.Foreground = (SolidColorBrush)Application.Current.Resources["SuccessBrush"];
            SetTwoFactorEnabledUi(false);
        }
        finally
        {
            DisableTwoFactorButton.IsEnabled = true;
        }
    }

    private void OnDisableTwoFactorClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "DisableTwoFactor");
        _ = OnDisableTwoFactorClick_Async();
    }

    // ---- Geräte-Registrierung ----

    private async Task OnRegisterDeviceClick_Async()
    {
        string name = NewDeviceNameBox.Text.Trim();
        string kind = (NewDeviceKindCombo.SelectedItem as ComboBoxItem)?.Tag as string ?? "esp32_node";
        if (string.IsNullOrWhiteSpace(name) || _client is null || _accessToken is null)
        {
            return;
        }

        RegisterDeviceButton.IsEnabled = false;
        try
        {
            var result = await _client.RegisterDeviceAsync(_accessToken, name, kind);
            if (!result.Success || result.ApiKey is null)
            {
                NewDeviceKeyText.Text = result.Error ?? "Registrierung fehlgeschlagen.";
                NewDeviceKeyText.Foreground = (SolidColorBrush)Application.Current.Resources["ErrorBrush"];
                NewDeviceKeyText.Visibility = Visibility.Visible;
                return;
            }

            NewDeviceNameBox.Text = string.Empty;
            NewDeviceKeyText.Text = $"API-Key (nur jetzt sichtbar, jetzt sichern!): {result.ApiKey}";
            NewDeviceKeyText.Foreground = (SolidColorBrush)Application.Current.Resources["SuccessBrush"];
            NewDeviceKeyText.Visibility = Visibility.Visible;
            await RefreshDevicesAsync();
        }
        finally
        {
            RegisterDeviceButton.IsEnabled = true;
        }
    }

    private void OnRegisterDeviceClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "RegisterDevice");
        _ = OnRegisterDeviceClick_Async();
    }

    // ---- Geräte-Löschen ----

    private void OnDeleteDeviceClick(object sender, RoutedEventArgs e)
    {
        InteractionLogger.Click("MeshDevicesPage", "DeleteDevice");
        if (sender is not Button { Tag: MeshServerClient.MeshDevice device })
        {
            return;
        }
        _ = ConfirmAndDeleteDeviceAsync(device);
    }

    /// <summary>
    /// Fragt IMMER erst per ContentDialog nach, bevor geloescht wird -
    /// unwiderruflich (der komplette Tracking-Verlauf des Geraets wird
    /// serverseitig mitgeloescht, siehe DeleteDeviceAsync/DELETE
    /// /devices/{id} in tarno-server/app/routers/devices.py).
    /// </summary>
    private async Task ConfirmAndDeleteDeviceAsync(MeshServerClient.MeshDevice device)
    {
        if (_client is null || _accessToken is null)
        {
            return;
        }

        var dialog = new ContentDialog
        {
            Title = "Gerät entfernen?",
            Content = $"„{device.Name}“ ({device.Kind}) wird endgültig entfernt, inklusive des kompletten " +
                      "Tracking-Verlaufs. Das lässt sich nicht rückgängig machen.",
            PrimaryButtonText = "Entfernen",
            CloseButtonText = "Abbrechen",
            DefaultButton = ContentDialogButton.Close,
            XamlRoot = this.XamlRoot,
        };

        var choice = await dialog.ShowAsync();
        if (choice != ContentDialogResult.Primary)
        {
            return;
        }

        var result = await _client.DeleteDeviceAsync(_accessToken, device.Id);
        if (!result.Success)
        {
            var errorDialog = new ContentDialog
            {
                Title = "Löschen fehlgeschlagen",
                Content = result.Error ?? "Unbekannter Fehler.",
                CloseButtonText = "OK",
                XamlRoot = this.XamlRoot,
            };
            await errorDialog.ShowAsync();
            return;
        }

        await RefreshDevicesAsync();
    }

    // ---- UI-Zustaende ----

    private void ShowLoggedInState()
    {
        LoginCard.Visibility = Visibility.Collapsed;
        AccountCard.Visibility = Visibility.Visible;
        TwoFactorCard.Visibility = Visibility.Visible;
        RegisterDeviceCard.Visibility = Visibility.Visible;
        DeviceListCard.Visibility = Visibility.Visible;

        // Login-Teilzustaende zuruecksetzen, falls man sich vorher ausgeloggt
        // und wieder eingeloggt hat.
        LoginCredentialsPanel.Visibility = Visibility.Visible;
        LoginTwoFactorPanel.Visibility = Visibility.Collapsed;
        PasswordResetPanel.Visibility = Visibility.Collapsed;
    }

    private void ShowLoggedOutState()
    {
        LoginCard.Visibility = Visibility.Visible;
        AccountCard.Visibility = Visibility.Collapsed;
        TwoFactorCard.Visibility = Visibility.Collapsed;
        RegisterDeviceCard.Visibility = Visibility.Collapsed;
        DeviceListCard.Visibility = Visibility.Collapsed;
        DeviceRowsPanel.Children.Clear();

        LoginCredentialsPanel.Visibility = Visibility.Visible;
        LoginTwoFactorPanel.Visibility = Visibility.Collapsed;
        PasswordResetPanel.Visibility = Visibility.Collapsed;
        _pendingTwoFactorToken = null;
        _pendingLoginEmail = null;

        // 2FA-Setup-Zwischenzustaende ebenfalls zuruecksetzen, damit ein
        // erneuter Login nicht mit einem alten QR-Code/Backup-Codes startet.
        TwoFactorSetupPanel.Visibility = Visibility.Collapsed;
        BackupCodesPanel.Visibility = Visibility.Collapsed;
        TwoFactorDisablePanel.Visibility = Visibility.Collapsed;
        StartTwoFactorSetupButton.Visibility = Visibility.Visible;
        TwoFactorStatusMessageText.Text = string.Empty;
    }

    private void BuildDeviceRows(System.Collections.Generic.IReadOnlyList<MeshServerClient.MeshDevice> devices)
    {
        DeviceRowsPanel.Children.Clear();
        DeviceListEmptyText.Visibility = devices.Count == 0 ? Visibility.Visible : Visibility.Collapsed;

        foreach (var device in devices.OrderByDescending(d => d.LastSeenAt ?? DateTimeOffset.MinValue))
        {
            bool online = device.LastSeenAt is { } lastSeen && DateTimeOffset.UtcNow - lastSeen < OnlineThreshold;

            var row = new Grid { ColumnSpacing = 12 };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(14) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var statusDot = new Microsoft.UI.Xaml.Shapes.Ellipse
            {
                Width = 10,
                Height = 10,
                VerticalAlignment = VerticalAlignment.Center,
                Fill = (SolidColorBrush)Application.Current.Resources[online ? "SuccessBrush" : "ErrorBrush"],
            };
            Grid.SetColumn(statusDot, 0);
            row.Children.Add(statusDot);

            var infoStack = new StackPanel { Spacing = 2, VerticalAlignment = VerticalAlignment.Center };
            infoStack.Children.Add(new TextBlock
            {
                Text = $"{device.Name}  ({device.Kind})",
                FontSize = 14,
                Foreground = (SolidColorBrush)Application.Current.Resources["TextPrimaryBrush"],
            });

            string lastSeenText = device.LastSeenAt is { } seen
                ? $"Zuletzt gesehen: {FormatRelative(seen)}"
                : "Noch nie gesehen";
            infoStack.Children.Add(new TextBlock
            {
                Text = lastSeenText,
                FontSize = 11,
                Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"],
            });

            if (!string.IsNullOrWhiteSpace(device.LastPayload))
            {
                infoStack.Children.Add(new TextBlock
                {
                    Text = FormatPayload(device.LastPayload),
                    FontSize = 11,
                    FontFamily = new FontFamily("Consolas"),
                    Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"],
                    TextWrapping = TextWrapping.Wrap,
                });
            }

            Grid.SetColumn(infoStack, 1);
            row.Children.Add(infoStack);

            var statusLabel = new TextBlock
            {
                Text = online ? "Online" : "Offline",
                FontSize = 12,
                VerticalAlignment = VerticalAlignment.Center,
                Foreground = (SolidColorBrush)Application.Current.Resources[online ? "SuccessBrush" : "TextMutedBrush"],
            };
            Grid.SetColumn(statusLabel, 2);
            row.Children.Add(statusLabel);

            // Loeschen-Button (Karteileichen/Duplikate entfernen, siehe
            // DeleteDeviceAsync-Kommentar) - Klick fragt IMMER erst per
            // ContentDialog nach, da unwiderruflich (der komplette Verlauf
            // dieses Geraets wird serverseitig mitgeloescht).
            var deleteButton = new Button
            {
                Content = new FontIcon { Glyph = "", FontSize = 14 }, // Delete-Symbol (Segoe Fluent Icons)
                Background = new SolidColorBrush(Microsoft.UI.Colors.Transparent),
                BorderThickness = new Thickness(0),
                Padding = new Thickness(6),
                VerticalAlignment = VerticalAlignment.Center,
                Tag = device,
            };
            ToolTipService.SetToolTip(deleteButton, "Gerät entfernen");
            deleteButton.Click += OnDeleteDeviceClick;
            Grid.SetColumn(deleteButton, 3);
            row.Children.Add(deleteButton);

            DeviceRowsPanel.Children.Add(row);
        }
    }

    /// <summary>
    /// last_payload ist serverseitig bewusst freies JSON (siehe DeviceSyncIn
    /// in tarno-server/app/schemas.py) - jeder Tracking-Typ bringt sein
    /// eigenes "type"-Feld mit. Hier werden die bekannten Typen (aktuell nur
    /// battery_network_status, siehe tarno-zte-app/.../TrackingService.kt)
    /// lesbar formatiert; alles Unbekannte faellt auf die rohe JSON-Zeile
    /// zurueck, damit auch kuenftige Tracking-Typen (App-Nutzung, Standort,
    /// ...) sofort sichtbar sind, bevor hier extra Code dafuer existiert.
    /// </summary>
    private static string FormatPayload(string rawPayload)
    {
        try
        {
            using var doc = JsonDocument.Parse(rawPayload);
            var root = doc.RootElement;
            string? type = root.TryGetProperty("type", out var t) ? t.GetString() : null;

            if (type == "battery_network_status")
            {
                int level = root.TryGetProperty("battery_level", out var lvl) ? lvl.GetInt32() : -1;
                bool charging = root.TryGetProperty("is_charging", out var c) && c.GetBoolean();
                string network = root.TryGetProperty("network_type", out var n) ? n.GetString() ?? "?" : "?";
                string batteryText = level >= 0 ? $"{level}%" : "?";
                string chargingText = charging ? " (laedt)" : "";
                return $"Akku {batteryText}{chargingText} - Netzwerk: {network}";
            }

            if (type == "location")
            {
                double lat = root.TryGetProperty("lat", out var la) ? la.GetDouble() : 0;
                double lon = root.TryGetProperty("lon", out var lo) ? lo.GetDouble() : 0;
                string accuracyText = root.TryGetProperty("accuracy_m", out var acc)
                    ? $" (±{acc.GetDouble():F0}m)"
                    : "";
                return $"Standort: {lat:F5}, {lon:F5}{accuracyText}";
            }

            if (type == "app_usage")
            {
                string pkg = root.TryGetProperty("foreground_package", out var fp) ? fp.GetString() ?? "?" : "?";
                return $"App-Fokus: {MeshDashboardPage.FriendlyAppName(pkg)}";
            }

            // Unbekannter Typ - roh anzeigen, aber wenigstens huebsch eingerueckt.
            return JsonSerializer.Serialize(root, new JsonSerializerOptions { WriteIndented = false });
        }
        catch (JsonException)
        {
            return rawPayload; // kein gueltiges JSON - unveraendert anzeigen statt abzustuerzen
        }
    }

    private static string FormatRelative(DateTimeOffset timestamp)
    {
        var delta = DateTimeOffset.UtcNow - timestamp;
        if (delta < TimeSpan.FromSeconds(90))
        {
            return $"vor {(int)delta.TotalSeconds}s";
        }
        if (delta < TimeSpan.FromMinutes(90))
        {
            return $"vor {(int)delta.TotalMinutes}min";
        }
        if (delta < TimeSpan.FromHours(48))
        {
            return $"vor {(int)delta.TotalHours}h";
        }
        return timestamp.LocalDateTime.ToString("dd.MM.yyyy HH:mm");
    }
}
