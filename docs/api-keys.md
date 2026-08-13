# API-Keys für TARNO einrichten

TARNO nutzt verschiedene KI-Dienste, für die du kostenlose oder kostenpflichtige API-Keys benötigst. Die Keys werden über den WinUI-Client in den Windows Credential Manager (bzw. den konfigurierten `SecretsVault` im Backend) geschrieben und niemals unverschlüsselt auf der Festplatte oder in Chat-Verläufen gespeichert. Optional funktioniert weiterhin das Setzen der passenden Umgebungsvariable.

## Unterstützte Provider

| Provider | Variable | Link |
|---|---|---|
| Mistral | `MISTRAL_API_KEY` | https://console.mistral.ai/api-keys |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| Gemini | `GEMINI_API_KEY` | https://aistudio.google.com/app/apikey |
| Groq | `GROQ_API_KEY` | https://console.groq.com/keys |
| Hugging Face | `HF_TOKEN` | https://huggingface.co/settings/tokens |
| Claude (Anthropic) | `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |
| Picovoice | `PICOVOICE_API_KEY` | https://console.picovoice.ai/ |

> **Empfehlung:** Für den Anfang reicht ein kostenloser `MISTRAL_API_KEY` oder ein `OPENAI_API_KEY`. Das Wake-Word läuft mit openWakeWord ohne Key.

## Empfohlenes Vorgehen: In-App-Login

1. Öffne TARNO und gehe zu **Einstellungen &gt; KI** (oder starte den First-Start-Wizard).
2. Klicke beim gewünschten Provider auf **"Holen"**.
3. Es öffnet sich ein WebView2-Dialog mit dem Provider-Login/Dashboard.
4. Melde dich beim Provider an und erstelle einen neuen API-Key.
5. Kopiere den Key in die Zwischenablage und klicke in TARNO auf **"Aus Zwischenablage einfügen"**.
6. TARNO füllt das Eingabefeld. Klicke auf **"Speichern"**, damit der Key im `SecretsVault` landet.

## Alternative: Umgebungsvariable

Falls du keinen WebView2-fähigen Browser auf dem System hast oder Key-Verwaltung automatisieren möchtest, kannst du die Variable wie bisher als Windows-Umgebungsvariable setzen:

1. Drücke die Windows-Taste und tippe `Umgebungsvariablen`.
2. Klicke auf **"Umgebungsvariablen für dieses Konto bearbeiten"**.
3. Im oberen Bereich (**Benutzervariablen**) klicke auf **"Neu..."**.
4. Gib als Namen die passende Variable ein (z. B. `MISTRAL_API_KEY`).
5. Füge den kopierten Key als Wert ein.
6. Klicke auf **OK**, dann nochmals **OK**, und starte TARNO neu.

## Picovoice-Key (nur für Wake-Word "porcupine")

1. Gehe zu https://console.picovoice.ai/ und melde dich an.
2. Kopiere deinen Access Key.
3. Lege ihn als `PICOVOICE_API_KEY` an.
4. Wähle im TARNO-Einstellungs- oder First-Start-Wizard das Wake-Word-Backend **porcupine** aus.

## Sicherheitshinweise

- Speichere Keys **nicht** im TARNO-Quellordner oder in Chat-Nachrichten.
- Teile Keys mit niemandem.
- Verwende für TARNO am besten einen separaten Key, den du bei Bedarf einfach widerrufen kannst.
- TARNO speichert Keys im `SecretsVault` (Standard-Backend: Windows Credential Manager / `keyring`) und liest zusätzlich die passende Umgebungsvariable als Fallback.
