using TARNO.UI.Services;
using TARNO.UI.ViewModels;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Navigation;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace TARNO.UI.Pages;

/// <summary>
/// Live-Uebersicht ueber alle Mesh-Geraete UND deren Tracking-Daten
/// gleichzeitig (Akku, Standort, App-Nutzung - siehe MeshDevice.LastPayloads
/// in MeshServerClient.cs). Ergaenzt MeshDevicesPage (die bleibt die
/// Verbindungs-/Account-/Registrierungs-Seite) um eine reine Anzeige-Seite,
/// die keinen Login-Flow noetig hat (nutzt den bereits vorhandenen
/// MeshCredentialStore-Token) - Login/Registrierung passiert weiterhin nur
/// auf MeshDevicesPage.
/// </summary>
public sealed partial class MeshDashboardPage : Page
{
    private static readonly TimeSpan OnlineThreshold = TimeSpan.FromSeconds(90);
    private static readonly TimeSpan AutoRefreshInterval = TimeSpan.FromSeconds(15);

    public MainViewModel ViewModel { get; private set; } = null!;

    private MeshServerClient? _client;
    private string? _accessToken;
    private DispatcherTimer? _refreshTimer;

    public MeshDashboardPage()
    {
        this.InitializeComponent();
    }

    protected override void OnNavigatedTo(NavigationEventArgs e)
    {
        if (e.Parameter is MainViewModel vm)
        {
            ViewModel = vm;
            var saved = MeshCredentialStore.LoadToken();
            if (saved is { } token)
            {
                _accessToken = token.AccessToken;
                _client = new MeshServerClient(ViewModel.Settings.MeshServerUrl);
                NotLoggedInCard.Visibility = Visibility.Collapsed;
                SummaryGrid.Visibility = Visibility.Visible;
                _ = RefreshAsync();
            }
            else
            {
                NotLoggedInCard.Visibility = Visibility.Visible;
                SummaryGrid.Visibility = Visibility.Collapsed;
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
                await RefreshAsync();
            }
        };
        _refreshTimer.Start();
    }

    private void StopAutoRefresh()
    {
        _refreshTimer?.Stop();
        _refreshTimer = null;
    }

    private async System.Threading.Tasks.Task RefreshAsync()
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
                // Token wirklich ungueltig (HTTP 401) - dieselbe Behandlung
                // wie MeshDevicesPage, User sieht auf dieser reinen Anzeige-
                // Seite dann einfach wieder die "Nicht eingeloggt"-Karte.
                _accessToken = null;
                MeshCredentialStore.Clear();
                NotLoggedInCard.Visibility = Visibility.Visible;
                SummaryGrid.Visibility = Visibility.Collapsed;
                DeviceCardsPanel.Items.Clear();
            }
            // KERNFIX: sonst (Netzwerkfehler, Server kurz down) NICHT
            // ausloggen - siehe ausfuehrlicher Kommentar in
            // MeshDevicesPage.xaml.cs.RefreshDevicesAsync(). Naechster
            // 15s-Auto-Refresh-Tick versucht es einfach erneut.
            return;
        }

        BuildDashboard(result.Devices);
    }

    private void BuildDashboard(IReadOnlyList<MeshServerClient.MeshDevice> devices)
    {
        int online = devices.Count(d => d.LastSeenAt is { } seen && DateTimeOffset.UtcNow - seen < OnlineThreshold);
        TotalCountText.Text = devices.Count.ToString();
        OnlineCountText.Text = online.ToString();
        OfflineCountText.Text = (devices.Count - online).ToString();

        EmptyText.Visibility = devices.Count == 0 ? Visibility.Visible : Visibility.Collapsed;

        var container = new StackPanel { Spacing = 16 };
        foreach (var device in devices.OrderByDescending(d => d.LastSeenAt ?? DateTimeOffset.MinValue))
        {
            container.Children.Add(BuildDeviceCard(device));
        }
        DeviceCardsPanel.Items.Clear();
        DeviceCardsPanel.Items.Add(container);
    }

    private Border BuildDeviceCard(MeshServerClient.MeshDevice device)
    {
        bool online = device.LastSeenAt is { } lastSeen && DateTimeOffset.UtcNow - lastSeen < OnlineThreshold;

        var stack = new StackPanel { Spacing = 12 };

        // Kopfzeile: Statuspunkt + Name/Art + Online-Label
        var header = new Grid { ColumnSpacing = 12 };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(14) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

        var statusDot = new Microsoft.UI.Xaml.Shapes.Ellipse
        {
            Width = 10,
            Height = 10,
            VerticalAlignment = VerticalAlignment.Center,
            Fill = (SolidColorBrush)Application.Current.Resources[online ? "SuccessBrush" : "ErrorBrush"],
        };
        Grid.SetColumn(statusDot, 0);
        header.Children.Add(statusDot);

        var titleStack = new StackPanel { Spacing = 2, VerticalAlignment = VerticalAlignment.Center };
        titleStack.Children.Add(new TextBlock
        {
            Text = $"{device.Name} ({device.Kind})",
            FontSize = 16,
            FontWeight = Microsoft.UI.Text.FontWeights.SemiBold,
            Foreground = (SolidColorBrush)Application.Current.Resources["TextPrimaryBrush"],
            TextWrapping = TextWrapping.Wrap,
            MaxLines = 2,
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        string lastSeenText = device.LastSeenAt is { } seen2 ? $"Zuletzt gesehen: {FormatRelative(seen2)}" : "Noch nie gesehen";
        titleStack.Children.Add(new TextBlock { Text = lastSeenText, FontSize = 11, Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"] });
        Grid.SetColumn(titleStack, 1);
        header.Children.Add(titleStack);

        var statusLabel = new TextBlock
        {
            Text = online ? "Online" : "Offline",
            FontSize = 12,
            VerticalAlignment = VerticalAlignment.Center,
            Foreground = (SolidColorBrush)Application.Current.Resources[online ? "SuccessBrush" : "TextMutedBrush"],
        };
        Grid.SetColumn(statusLabel, 2);
        header.Children.Add(statusLabel);

        stack.Children.Add(header);

        // Tracking-Sektionen: eine Zeile pro bekanntem Typ in LastPayloads,
        // gleichzeitig sichtbar statt nur der zuletzt eingetroffene.
        if (device.LastPayloads is { Count: > 0 } payloads)
        {
            var grid = new Grid { ColumnSpacing = 24, RowSpacing = 8 };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });

            AddTrackingTile(grid, 0, "", "Akku & Netzwerk", FormatBatteryTile(payloads, "battery_network_status"));
            var locationTextBlock = AddTrackingTile(grid, 1, "", "Standort", FormatLocationTile(payloads, "location"));
            AddTrackingTile(grid, 2, "", "App-Fokus", FormatAppUsageTile(payloads, "app_usage"));

            stack.Children.Add(grid);

            // Rohe Koordinaten sind fuer Menschen nicht lesbar - Adresse per
            // Reverse-Geocoding nachladen (async, blockiert den Kartenaufbau
            // nicht) und den Text danach austauschen. Fallback bei Fehler/
            // Timeout bleibt einfach bei "lat, lon" stehen statt eines Fehlers.
            if (locationTextBlock is not null && payloads.TryGetValue("location", out var locEntry))
            {
                var lp = locEntry.Payload;
                if (lp.TryGetProperty("lat", out var latEl) && lp.TryGetProperty("lon", out var lonEl))
                {
                    double lat = latEl.GetDouble();
                    double lon = lonEl.GetDouble();
                    _ = UpdateLocationTextWithAddressAsync(locationTextBlock, lat, lon);
                }
            }
        }
        else
        {
            stack.Children.Add(new TextBlock
            {
                Text = "Noch keine Tracking-Daten von diesem Geraet.",
                FontSize = 12,
                Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"],
            });
        }

        return new Border { Style = (Style)Application.Current.Resources["GlassCardStyle"], Child = stack };
    }

    private static TextBlock AddTrackingTile(Grid grid, int column, string glyph, string title, (string Text, string? SubText, bool HasData) content)
    {
        var tile = new StackPanel { Spacing = 4 };
        var titleRow = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6 };
        titleRow.Children.Add(new TextBlock
        {
            Text = glyph,
            FontFamily = (FontFamily)Application.Current.Resources["SymbolThemeFontFamily"],
            FontSize = 14,
            Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"],
        });
        titleRow.Children.Add(new TextBlock { Text = title, FontSize = 12, Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"] });
        tile.Children.Add(titleRow);

        var contentTextBlock = new TextBlock
        {
            Text = content.Text,
            FontSize = 14,
            TextWrapping = TextWrapping.Wrap,
            Foreground = (SolidColorBrush)Application.Current.Resources[content.HasData ? "TextPrimaryBrush" : "TextMutedBrush"],
        };
        tile.Children.Add(contentTextBlock);
        if (content.SubText is not null)
        {
            tile.Children.Add(new TextBlock
            {
                Text = content.SubText,
                FontSize = 11,
                Foreground = (SolidColorBrush)Application.Current.Resources["TextMutedBrush"],
            });
        }

        Grid.SetColumn(tile, column);
        grid.Children.Add(tile);
        return contentTextBlock;
    }

    private static readonly HttpClient GeocodeHttpClient = new() { Timeout = TimeSpan.FromSeconds(6) };
    private static readonly Dictionary<(int, int), string> GeocodeCache = new();

    /// <summary>Reverse-Geocoding ueber OpenStreetMap Nominatim (kein API-Key
    /// noetig, kostenlos) statt roher "lat, lon"-Zahlen, die fuer den Nutzer
    /// nicht lesbar sind - explizit vom Nutzer so gewaehlt (Alternative waere
    /// ein reiner "In Karte oeffnen"-Link ohne automatische Drittanbieter-
    /// Uebertragung gewesen). Auf ~4 Nachkommastellen gerundeter Cache pro
    /// Prozesslaufzeit, damit der alle 15s tickende Dashboard-Refresh nicht
    /// bei jedem Tick erneut denselben Ort abfragt (Nominatims Nutzungsregeln
    /// verlangen max. 1 Anfrage/Sekunde). User-Agent-Header ist bei Nominatim
    /// Pflicht, sonst wird die Anfrage abgelehnt. Bricht die UI nicht ab, wenn
    /// die Anfrage fehlschlaegt/timeout - Text bleibt dann einfach bei den
    /// Koordinaten stehen, kein Fehlerzustand sichtbar.</summary>
    private static async Task UpdateLocationTextWithAddressAsync(TextBlock textBlock, double lat, double lon)
    {
        var cacheKey = ((int)Math.Round(lat * 10000), (int)Math.Round(lon * 10000));
        if (GeocodeCache.TryGetValue(cacheKey, out var cached))
        {
            textBlock.Text = cached;
            return;
        }

        try
        {
            var url = $"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat.ToString(System.Globalization.CultureInfo.InvariantCulture)}&lon={lon.ToString(System.Globalization.CultureInfo.InvariantCulture)}&zoom=16";
            using var request = new HttpRequestMessage(HttpMethod.Get, url);
            request.Headers.UserAgent.ParseAdd("TARNO-Mesh-Dashboard/1.0 (privates Projekt)");
            using var response = await GeocodeHttpClient.SendAsync(request);
            if (!response.IsSuccessStatusCode)
            {
                return;
            }
            using var stream = await response.Content.ReadAsStreamAsync();
            using var doc = await System.Text.Json.JsonDocument.ParseAsync(stream);
            string? address = doc.RootElement.TryGetProperty("display_name", out var dn) ? dn.GetString() : null;
            if (string.IsNullOrWhiteSpace(address))
            {
                return;
            }

            GeocodeCache[cacheKey] = address;
            textBlock.Text = address;
        }
        catch
        {
            // Netzwerkfehler/Timeout - Koordinaten-Anzeige bleibt einfach stehen.
        }
    }

    private static (string, string?, bool) FormatBatteryTile(IReadOnlyDictionary<string, MeshServerClient.DeviceTrackingEntry> payloads, string key)
    {
        if (!payloads.TryGetValue(key, out var entry)) return ("Keine Daten", null, false);
        var p = entry.Payload;
        int level = p.TryGetProperty("battery_level", out var l) ? l.GetInt32() : -1;
        bool charging = p.TryGetProperty("is_charging", out var c) && c.GetBoolean();
        string network = p.TryGetProperty("network_type", out var n) ? n.GetString() ?? "?" : "?";
        string text = level >= 0 ? $"{level}%{(charging ? " (laedt)" : "")} - {network}" : "Keine Daten";
        return (text, $"vor {FormatRelative(entry.SyncedAt)}", true);
    }

    private static (string, string?, bool) FormatLocationTile(IReadOnlyDictionary<string, MeshServerClient.DeviceTrackingEntry> payloads, string key)
    {
        if (!payloads.TryGetValue(key, out var entry)) return ("Keine Daten", null, false);
        var p = entry.Payload;
        double lat = p.TryGetProperty("lat", out var la) ? la.GetDouble() : 0;
        double lon = p.TryGetProperty("lon", out var lo) ? lo.GetDouble() : 0;
        return ($"{lat:F5}, {lon:F5}", $"vor {FormatRelative(entry.SyncedAt)}", true);
    }

    private static (string, string?, bool) FormatAppUsageTile(IReadOnlyDictionary<string, MeshServerClient.DeviceTrackingEntry> payloads, string key)
    {
        if (!payloads.TryGetValue(key, out var entry)) return ("Keine Daten", null, false);
        var p = entry.Payload;
        string pkg = p.TryGetProperty("foreground_package", out var fp) ? fp.GetString() ?? "?" : "?";
        return (FriendlyAppName(pkg), $"vor {FormatRelative(entry.SyncedAt)}", true);
    }

    /// <summary>Rohe Android-Package-Namen (z.B. "com.zhiliaoapp.musically" fuer
    /// TikTok) sind fuer den Nutzer nicht erkennbar - kleine, bewusst nicht
    /// vollstaendige Zuordnungstabelle der haeufigsten Alltags-Apps statt
    /// eines vollen Package-Manager-Lookups (der ginge nur auf dem Handy
    /// selbst, nicht hier auf dem Desktop). Unbekannte Packages zeigen
    /// weiterhin den rohen Namen - besser als eine falsche Vermutung.</summary>
    private static readonly Dictionary<string, string> KnownAppNames = new()
    {
        ["com.zhiliaoapp.musically"] = "TikTok",
        ["com.whatsapp"] = "WhatsApp",
        ["com.instagram.android"] = "Instagram",
        ["com.google.android.youtube"] = "YouTube",
        ["com.google.android.apps.maps"] = "Google Maps",
        ["com.android.chrome"] = "Chrome",
        ["com.facebook.katana"] = "Facebook",
        ["com.snapchat.android"] = "Snapchat",
        ["com.spotify.music"] = "Spotify",
        ["com.google.android.gm"] = "Gmail",
        ["com.twitter.android"] = "X (Twitter)",
        ["org.telegram.messenger"] = "Telegram",
        ["com.discord"] = "Discord",
    };

    /// <summary>internal statt private - auch von MeshDevicesPage.FormatPayload
    /// genutzt, damit App-Namen an beiden Stellen konsistent lesbar sind.</summary>
    internal static string FriendlyAppName(string packageName) =>
        KnownAppNames.TryGetValue(packageName, out var friendly) ? friendly : packageName;

    private static string FormatRelative(DateTimeOffset timestamp)
    {
        var delta = DateTimeOffset.UtcNow - timestamp;
        if (delta < TimeSpan.FromSeconds(90)) return $"{(int)delta.TotalSeconds}s";
        if (delta < TimeSpan.FromMinutes(90)) return $"{(int)delta.TotalMinutes}min";
        if (delta < TimeSpan.FromHours(48)) return $"{(int)delta.TotalHours}h";
        return timestamp.LocalDateTime.ToString("dd.MM.yyyy HH:mm");
    }
}
