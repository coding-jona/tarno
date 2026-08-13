using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

namespace TARNO.UI.Services;

/// <summary>
/// Schlanker HTTP-Client fuer den Tarno-Server (siehe tarno-server/README.md
/// im Repo-Root). Spiegelt bewusst ApiClient.kt aus der Android-App (gleiches
/// Server-API, gleiche Feldnamen) - beide Clients sollten bei jeder
/// Server-Aenderung gegen tarno-server/tools/verify_android_contract.py
/// (bzw. ein analoges .NET-Pendant) gegengeprueft werden.
///
/// Laeuft komplett unabhaengig vom bestehenden gRPC-Kanal zum Python-Backend
/// (GrpcClientService) - der Tarno-Server ist ein eigener REST-Dienst, kein
/// Teil des bestehenden IPC-Vertrags. Aendert also nichts an der
/// bestehenden Backend-Kommunikation.
/// </summary>
public sealed class MeshServerClient : IDisposable
{
    private readonly HttpClient _http;

    public MeshServerClient(string baseUrl)
    {
        _http = new HttpClient
        {
            BaseAddress = new Uri(baseUrl.TrimEnd('/') + "/"),
            Timeout = TimeSpan.FromSeconds(10),
        };
    }

    /// <summary>
    /// AccessToken gesetzt -> fertig eingeloggt (kein 2FA aktiv, oder gar
    /// nicht erst noetig). RequiresTwoFactor+PendingToken gesetzt -> Passwort
    /// war korrekt, aber der Account hat 2FA aktiv - PendingToken gegen
    /// VerifyTwoFactorAsync eintauschen. Genau eine der beiden Gruppen ist
    /// belegt, ausser bei Success=false.
    /// </summary>
    public sealed record LoginResult(bool Success, string? AccessToken, bool RequiresTwoFactor, string? PendingToken, string? Error);
    public sealed record RegisterResult(bool Success, string? Error);
    public sealed record TwoFactorSetupResult(bool Success, string? Secret, string? ProvisioningUri, string? QrCodeBase64Png, string? Error);
    public sealed record TwoFactorEnableResult(bool Success, IReadOnlyList<string> BackupCodes, string? Error);
    public sealed record SimpleResult(bool Success, string? Error);
    /// <summary>Ein einzelner Tracking-Sync-Eintrag innerhalb von MeshDevice.LastPayloads -
    /// spiegelt das {"payload": {...}, "synced_at": iso}-Objekt aus tarno-server/app/routers/devices.py.</summary>
    public sealed record DeviceTrackingEntry(
        [property: JsonPropertyName("payload")] JsonElement Payload,
        [property: JsonPropertyName("synced_at")] DateTimeOffset SyncedAt);

    public sealed record MeshDevice(
        [property: JsonPropertyName("id")] string Id,
        [property: JsonPropertyName("name")] string Name,
        [property: JsonPropertyName("kind")] string Kind,
        [property: JsonPropertyName("last_seen_at")] DateTimeOffset? LastSeenAt,
        [property: JsonPropertyName("last_payload")] string? LastPayload,
        // Ein Slot PRO Tracking-Typ (battery_network_status/location/app_usage/...)
        // statt nur des zuletzt eingetroffenen - siehe last_payloads in
        // tarno-server/app/models.py fuer die Begruendung. Null bei Geraeten,
        // die noch nie gesynct haben.
        [property: JsonPropertyName("last_payloads")] IReadOnlyDictionary<string, DeviceTrackingEntry>? LastPayloads,
        [property: JsonPropertyName("created_at")] DateTimeOffset CreatedAt);
    /// <summary>KERNFIX: IsUnauthorized unterscheidet "Token wirklich ungueltig"
    /// (HTTP 401 - z.B. abgelaufen, oder Server-DB wurde zurueckgesetzt) von
    /// jedem anderen Fehlschlag (Netzwerk-Timeout, DNS-Fehler, Server kurz
    /// neu gestartet, 5xx). Vorher loeschten Aufrufer bei JEDEM Success=false
    /// den gespeicherten Login (MeshCredentialStore.Clear()) - ein einziger
    /// kurzer Verbindungsaussetzer (z.B. Cloudflare-Tunnel-Neustart) reichte,
    /// um den Nutzer dauerhaft auszuloggen, obwohl der Token noch gueltig war.
    /// Nur bei echtem 401 soll der Login entfernt werden.</summary>
    public sealed record DeviceListResult(bool Success, IReadOnlyList<MeshDevice> Devices, string? Error, bool IsUnauthorized = false);
    public sealed record RegisterDeviceResult(bool Success, MeshDevice? Device, string? ApiKey, string? Error);

    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };

    public async Task<LoginResult> LoginAsync(string email, string password)
    {
        var form = new FormUrlEncodedContent(new Dictionary<string, string>
        {
            ["username"] = email,
            ["password"] = password,
        });

        try
        {
            using var response = await _http.PostAsync("auth/login", form);
            string body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                return new LoginResult(false, null, false, null, ExtractDetailOrDefault(body, $"Login fehlgeschlagen (HTTP {(int)response.StatusCode})"));
            }

            using var doc = JsonDocument.Parse(body);
            bool requiresTwoFactor = doc.RootElement.TryGetProperty("requires_2fa", out var rtf) && rtf.GetBoolean();
            if (requiresTwoFactor)
            {
                string? pendingToken = doc.RootElement.TryGetProperty("pending_token", out var pt) ? pt.GetString() : null;
                if (pendingToken is null)
                {
                    return new LoginResult(false, null, false, null, "Server-Antwort ohne pending_token trotz requires_2fa");
                }
                return new LoginResult(true, null, true, pendingToken, null);
            }

            if (!doc.RootElement.TryGetProperty("access_token", out var tokenElement) || tokenElement.GetString() is not { } token)
            {
                return new LoginResult(false, null, false, null, "Server-Antwort ohne access_token");
            }
            return new LoginResult(true, token, false, null, null);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new LoginResult(false, null, false, null, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    /// <summary>Tauscht den PendingToken aus LoginAsync gegen den echten
    /// AccessToken ein, wenn der TOTP-/Backup-Code stimmt.</summary>
    public async Task<LoginResult> VerifyTwoFactorAsync(string pendingToken, string code)
    {
        var payload = JsonSerializer.Serialize(new { pending_token = pendingToken, code });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");

        try
        {
            using var response = await _http.PostAsync("auth/login/verify-2fa", content);
            string body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                return new LoginResult(false, null, false, null, ExtractDetailOrDefault(body, $"Code falsch (HTTP {(int)response.StatusCode})"));
            }

            using var doc = JsonDocument.Parse(body);
            if (!doc.RootElement.TryGetProperty("access_token", out var tokenElement) || tokenElement.GetString() is not { } token)
            {
                return new LoginResult(false, null, false, null, "Server-Antwort ohne access_token");
            }
            return new LoginResult(true, token, false, null, null);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new LoginResult(false, null, false, null, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    /// <summary>Setzt ein neues Passwort per TOTP- oder Backup-Code (kein
    /// E-Mail-Versand eingerichtet, siehe tarno-server/README.md). Verlangt,
    /// dass der Account 2FA aktiviert hat.</summary>
    public async Task<SimpleResult> ResetPasswordAsync(string email, string code, string newPassword)
    {
        var payload = JsonSerializer.Serialize(new { email, code, new_password = newPassword });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");

        try
        {
            using var response = await _http.PostAsync("auth/password-reset", content);
            if (response.IsSuccessStatusCode)
            {
                return new SimpleResult(true, null);
            }
            string body = await response.Content.ReadAsStringAsync();
            return new SimpleResult(false, ExtractDetailOrDefault(body, $"Zurücksetzen fehlgeschlagen (HTTP {(int)response.StatusCode})"));
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new SimpleResult(false, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    public async Task<TwoFactorSetupResult> SetupTwoFactorAsync(string accessToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "auth/2fa/setup");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        try
        {
            using var response = await _http.SendAsync(request);
            string body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                return new TwoFactorSetupResult(false, null, null, null, ExtractDetailOrDefault(body, $"Setup fehlgeschlagen (HTTP {(int)response.StatusCode})"));
            }

            using var doc = JsonDocument.Parse(body);
            string? secret = doc.RootElement.TryGetProperty("secret", out var s) ? s.GetString() : null;
            string? uri = doc.RootElement.TryGetProperty("provisioning_uri", out var u) ? u.GetString() : null;
            string? qr = doc.RootElement.TryGetProperty("qr_code_base64", out var q) ? q.GetString() : null;
            return new TwoFactorSetupResult(true, secret, uri, qr, null);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new TwoFactorSetupResult(false, null, null, null, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    /// <summary>Bestaetigt den Code aus SetupTwoFactorAsync, schaltet 2FA
    /// scharf, liefert 10 Backup-Codes (nur JETZT sichtbar - danach nie
    /// wieder abrufbar, wie ein Passwort).</summary>
    public async Task<TwoFactorEnableResult> EnableTwoFactorAsync(string accessToken, string code)
    {
        var payload = JsonSerializer.Serialize(new { code });
        using var request = new HttpRequestMessage(HttpMethod.Post, "auth/2fa/enable")
        {
            Content = new StringContent(payload, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        try
        {
            using var response = await _http.SendAsync(request);
            string body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                return new TwoFactorEnableResult(false, Array.Empty<string>(), ExtractDetailOrDefault(body, $"Aktivierung fehlgeschlagen (HTTP {(int)response.StatusCode})"));
            }

            using var doc = JsonDocument.Parse(body);
            var codes = new List<string>();
            if (doc.RootElement.TryGetProperty("backup_codes", out var arr) && arr.ValueKind == JsonValueKind.Array)
            {
                foreach (var item in arr.EnumerateArray())
                {
                    if (item.GetString() is { } c) codes.Add(c);
                }
            }
            return new TwoFactorEnableResult(true, codes, null);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new TwoFactorEnableResult(false, Array.Empty<string>(), $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    /// <summary>Braucht bewusst nochmal einen gueltigen Code (TOTP oder
    /// Backup) - ein gestohlener Access-Token allein darf 2FA nicht
    /// abschalten koennen, siehe tarno-server/app/routers/auth.py.</summary>
    public async Task<SimpleResult> DisableTwoFactorAsync(string accessToken, string code)
    {
        var payload = JsonSerializer.Serialize(new { code });
        using var request = new HttpRequestMessage(HttpMethod.Post, "auth/2fa/disable")
        {
            Content = new StringContent(payload, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        try
        {
            using var response = await _http.SendAsync(request);
            if (response.IsSuccessStatusCode)
            {
                return new SimpleResult(true, null);
            }
            string body = await response.Content.ReadAsStringAsync();
            return new SimpleResult(false, ExtractDetailOrDefault(body, $"Deaktivierung fehlgeschlagen (HTTP {(int)response.StatusCode})"));
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new SimpleResult(false, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    public async Task<RegisterResult> RegisterAsync(string email, string password)
    {
        var payload = JsonSerializer.Serialize(new { email, password });
        using var content = new StringContent(payload, Encoding.UTF8, "application/json");

        try
        {
            using var response = await _http.PostAsync("auth/register", content);
            if (response.IsSuccessStatusCode)
            {
                return new RegisterResult(true, null);
            }
            string body = await response.Content.ReadAsStringAsync();
            return new RegisterResult(false, ExtractDetailOrDefault(body, $"Registrierung fehlgeschlagen (HTTP {(int)response.StatusCode})"));
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new RegisterResult(false, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    public sealed record MeResult(bool Success, string? Email, bool TotpEnabled, string? Error);

    public async Task<MeResult> GetMeAsync(string accessToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "auth/me");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        try
        {
            using var response = await _http.SendAsync(request);
            string body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                return new MeResult(false, null, false, ExtractDetailOrDefault(body, $"Abruf fehlgeschlagen (HTTP {(int)response.StatusCode})"));
            }

            using var doc = JsonDocument.Parse(body);
            string? email = doc.RootElement.TryGetProperty("email", out var e) ? e.GetString() : null;
            bool totpEnabled = doc.RootElement.TryGetProperty("totp_enabled", out var t) && t.GetBoolean();
            return new MeResult(true, email, totpEnabled, null);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new MeResult(false, null, false, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    public async Task<DeviceListResult> ListDevicesAsync(string accessToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Get, "devices");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        try
        {
            using var response = await _http.SendAsync(request);
            string body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                bool unauthorized = response.StatusCode == System.Net.HttpStatusCode.Unauthorized;
                return new DeviceListResult(false, Array.Empty<MeshDevice>(), ExtractDetailOrDefault(body, $"Abruf fehlgeschlagen (HTTP {(int)response.StatusCode})"), unauthorized);
            }

            var devices = JsonSerializer.Deserialize<List<MeshDevice>>(body, JsonOptions) ?? new List<MeshDevice>();
            return new DeviceListResult(true, devices, null);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            // Netzwerkfehler (DNS, Timeout, Server nicht erreichbar) ist KEIN
            // "Token ungueltig" - IsUnauthorized bleibt bewusst false (Default).
            return new DeviceListResult(false, Array.Empty<MeshDevice>(), $"Verbindung fehlgeschlagen: {ex.Message}");
        }
        catch (JsonException ex)
        {
            return new DeviceListResult(false, Array.Empty<MeshDevice>(), $"Antwort nicht lesbar: {ex.Message}");
        }
    }

    /// <summary>
    /// Registriert ein neues Geraet. Der zurueckgegebene api_key wird vom
    /// Server nur EINMAL herausgegeben (siehe DeviceCreatedOut in
    /// tarno-server/app/schemas.py) - muss dem Nutzer sofort angezeigt und
    /// von ihm selbst gesichert werden (z.B. fuer die ESP32-Firmware-Config).
    /// </summary>
    public async Task<RegisterDeviceResult> RegisterDeviceAsync(string accessToken, string name, string kind)
    {
        var payload = JsonSerializer.Serialize(new { name, kind });
        using var request = new HttpRequestMessage(HttpMethod.Post, "devices")
        {
            Content = new StringContent(payload, Encoding.UTF8, "application/json"),
        };
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        try
        {
            using var response = await _http.SendAsync(request);
            string body = await response.Content.ReadAsStringAsync();
            if (!response.IsSuccessStatusCode)
            {
                return new RegisterDeviceResult(false, null, null, ExtractDetailOrDefault(body, $"Registrierung fehlgeschlagen (HTTP {(int)response.StatusCode})"));
            }

            using var doc = JsonDocument.Parse(body);
            var device = JsonSerializer.Deserialize<MeshDevice>(body, JsonOptions);
            string? apiKey = doc.RootElement.TryGetProperty("api_key", out var keyElement) ? keyElement.GetString() : null;
            return new RegisterDeviceResult(true, device, apiKey, null);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new RegisterDeviceResult(false, null, null, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
        catch (JsonException ex)
        {
            return new RegisterDeviceResult(false, null, null, $"Antwort nicht lesbar: {ex.Message}");
        }
    }

    /// <summary>
    /// Loescht ein Geraet endgueltig (server-seitig DELETE /devices/{id},
    /// siehe tarno-server/app/routers/devices.py) - fuer Karteileichen/
    /// Duplikate, z.B. wenn ein ESP32 bei jeder Neu-Provisionierung eine neue
    /// Geraete-ID bekommt und alte Eintraege verwaist zurueckbleiben.
    /// </summary>
    public async Task<SimpleResult> DeleteDeviceAsync(string accessToken, string deviceId)
    {
        using var request = new HttpRequestMessage(HttpMethod.Delete, $"devices/{deviceId}");
        request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", accessToken);

        try
        {
            using var response = await _http.SendAsync(request);
            if (response.IsSuccessStatusCode)
            {
                return new SimpleResult(true, null);
            }
            string body = await response.Content.ReadAsStringAsync();
            return new SimpleResult(false, ExtractDetailOrDefault(body, $"Loeschen fehlgeschlagen (HTTP {(int)response.StatusCode})"));
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            return new SimpleResult(false, $"Verbindung fehlgeschlagen: {ex.Message}");
        }
    }

    private static string ExtractDetailOrDefault(string body, string fallback)
    {
        try
        {
            using var doc = JsonDocument.Parse(body);
            if (doc.RootElement.TryGetProperty("detail", out var detail) && detail.ValueKind == JsonValueKind.String)
            {
                return detail.GetString() ?? fallback;
            }
        }
        catch (JsonException)
        {
            // Antwort war kein JSON (z.B. reiner Verbindungsfehler-Text) - Fallback nutzen.
        }
        return fallback;
    }

    public void Dispose() => _http.Dispose();
}
