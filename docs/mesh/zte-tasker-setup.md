# Node A: ZTE Blade V70 — Tasker/MacroDroid Setup

Manuelle Einrichtung auf dem Handy — **kann nicht automatisiert werden**, du
musst das selbst auf dem ZTE anwenden. Ziel: bei Display-/Akku-/WLAN-Änderungen
einen UDP-Broadcast senden, der von `tarno/integrations/mesh/udp_listener.py`
auf dem PC empfangen wird.

**Ziel-Format** (muss exakt passen, siehe `tarno/integrations/mesh/payload.py`):
```json
{
  "sender_node": "ZTE_BLADE_V70",
  "target_hub": "DYNAMIC_BROADCAST",
  "timestamp": 1718000000,
  "event_type": "USER_STATE_CHANGE",
  "payload": {
    "screen_state": "ON",
    "battery_level": 78,
    "current_wifi_bssid": "AA:BB:CC:DD:EE:FF",
    "rssi": -55
  }
}
```
- **Ziel-Adresse:** `255.255.255.255` (Broadcast — kein feste Hub-IP nötig)
- **Ziel-Port:** `47800` (muss mit `MeshConfig.udp_port` übereinstimmen)

## Option A: MacroDroid (empfohlen, einfacher)

MacroDroid hat eine eingebaute **"Send UDP Message"**-Aktion — kein Plugin nötig.

1. **Neues Makro erstellen** → Trigger auswählen:
   - `Display On` / `Display Off` (unter "Device Events")
   - `Battery Level` (unter "Device Events", Trigger bei jeder %-Änderung wählen falls verfügbar, sonst feste Schwellen z.B. alle 10%)
   - `WiFi Connected` / `WiFi Disconnected` (unter "Connectivity Events")
2. **Aktion hinzufügen** → **"Send UDP Message"** (unter "Connectivity"):
   - IP-Adresse: `255.255.255.255`
   - Port: `47800`
   - Nachricht (Text-Feld, MacroDroid-Variablen nutzen):
     ```
     {"sender_node":"ZTE_BLADE_V70","target_hub":"DYNAMIC_BROADCAST","timestamp":[unix_epoch],"event_type":"USER_STATE_CHANGE","payload":{"screen_state":"[display_state]","battery_level":[battery_level],"current_wifi_bssid":"[wifi_bssid]","rssi":[wifi_rssi]}}
     ```
     (MacroDroid-Variablen in `[eckigen Klammern]` durch die tatsächlichen lokalen Variablennamen ersetzen — Battery/WiFi-Werte stehen in MacroDroid unter "Local Variables" beim Trigger zur Verfügung, `unix_epoch` z.B. über die eingebaute `%time_epoch%`-Variable.)
3. Makro aktivieren, Akku-Optimierung für MacroDroid **deaktivieren** (Android-Einstellungen → Apps → MacroDroid → Akku → "Nicht optimieren"), sonst killt Android den Hintergrunddienst.

## Option B: Tasker

1. **Neues Profil** → State/Event-Trigger:
   - `Display State` (Ein/Aus)
   - `Battery Level` (mit gewünschter Schrittweite)
   - `WiFi Connected`
2. **Task** mit **"Send Intent"**-Aktion, oder das Plugin **"AutoRemote"**/**"Send UDP"** aus dem Play Store installieren (Tasker selbst hat kein natives UDP-Send, anders als MacroDroid) — dann analog zu Option A konfigurieren: Ziel `255.255.255.255:47800`, gleicher JSON-Body über Tasker-Variablen (`%WIFII` für BSSID, `%BATT` für Akku, etc.).
3. **Battery-Optimierungs-Ausnahme** für Tasker setzen (wie bei MacroDroid).

## Testen

Auf dem PC, während `python -m tarno` mit `mesh.enabled: true` läuft:
```
py -3.12 tools/mesh_mock_sender.py --scenario pc_fallback  # zum Vergleich, wie ein echtes Paket aussehen soll
```
Dann das Makro/Profil auf dem Handy manuell auslösen (Display an/aus) und in TARNOs Logs nach `Mesh-UDP-Listener` bzw. `MeshNodeSeenEvent` suchen — falls es ankommt, war die Einrichtung korrekt.

**Ich kann diesen Schritt nicht für dich verifizieren** — kein Zugriff auf dein Handy. Bitte selbst bestätigen, dass Pakete ankommen.
