# ADR-006: API-Key-Provider-Onboarding über WebView2

## Status

Entschieden, implementiert.

## Kontext

TARNO braucht API-Keys für KI-Provider (Mistral, OpenAI, Gemini, Groq, Hugging Face, Claude). Bisher mussten Nutzer Keys manuell im Browser generieren, in die Zwischenablage kopieren und im TARNO-Fenster einfügen. Das führte zu hoher Reibung und Support-Aufwand.

Folgende Alternativen wurden geprüft:

1. **Echtes OAuth 2.0 / OAuth2Manager**
   - OpenAI und Mistral bieten keinen öffentlichen End-User-OAuth für API-Zugriff.
   - Gemini OAuth würde einen Google-Cloud-Client und Consent-Screen erfordern.
2. **Systembrowser-Deep-Link mit anschließendem Clipboard-Scan**
   - Nutzer verlässt die App, fehleranfällig.
3. **Browser-Automatisierung / DOM-Scraping im WebView2**
   - Brüchig und potenziell gegen Provider-ToS.
4. **WebView2-Dialog mit manuellem Copy/Paste aus der Zwischenablage**
   - Nutzer bleibt in der App, behält volle Kontrolle, keine DOM-Abhängigkeit.

## Entscheidung

Wir verwenden einen modalen WebView2-Dialog pro Provider. Der Dialog lädt das Provider-Dashboard. Der Nutzer loggt sich ein, kopiert den API-Key mit dem Provider-eigenen Copy-Button und fügt ihn in TARNO über "Aus Zwischenablage einfügen" ein. TARNO prüft das Key-Format anhand eines Regex, bevor es das Eingabefeld füllt.

## Konsequenzen

- Keine OAuth-Client-Registrierung nötig.
- Alle unterstützten API-Key-Provider funktionieren gleichermaßen.
- Provider-DOM-Änderungen beeinflussen die App nicht.
- Der NSIS-Installer lädt die WebView2 Runtime bei Bedarf über den Microsoft-Evergreen-Bootstrapper herunter (Internetverbindung erforderlich).
- Nutzer muss den Provider eigenständig im Dialog authentifizieren.
- Phishing-Risiko im eingebetteten Browser liegt beim Nutzer; TARNO zeigt die aktuelle URL.

## Betroffene Dateien

- `src/TARNO.UI/Assets/provider_onboarding.json`
- `src/TARNO.UI/Models/ProviderOnboardingInfo.cs`
- `src/TARNO.UI/Services/ProviderOnboardingService.cs`
- `src/TARNO.UI/Dialogs/ProviderLoginDialog.xaml` + `.cs`
- `src/TARNO.UI/Pages/SettingsPage.xaml.cs`
- `src/TARNO.UI/Dialogs/FirstStartWizardDialog.xaml.cs`
- `tarno/ai/factory.py`
- `docs/api-keys.md`
