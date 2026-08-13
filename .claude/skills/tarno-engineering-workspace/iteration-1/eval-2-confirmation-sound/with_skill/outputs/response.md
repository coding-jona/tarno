## Bestätigungston statt "Ja, Sir?" — Übersicht der nötigen Änderungen

Das gesprochene "Ja, Sir?" wird an **4 Stellen** im Code ausgelöst — eine pro Launch-Modus. Alle vier müssen geändert werden, damit der Bestätigungston in jedem Modus funktioniert.

### Die 4 Stellen, die geändert werden müssen

1. **`jarvis/core/engine.py`**, Zeile 155 — Standalone-Console-Modus (`--voice`)
   ```python
   self.synthesizer.speak("Ja, Sir?")
   ```

2. **`jarvis/voice/voice_service.py`**, Zeile 94 — VoiceService (Framework-agnostisch)
   ```python
   self._synthesizer.speak("Ja, Sir?")
   ```

3. **`jarvis/core/service_mediator.py`**, Zeile 264 — PySide6-GUI-Modus
   ```python
   Q_ARG(str, "Ja, Sir?"),
   ```

4. **`jarvis/grpc/server.py`**, Zeile 277 — gRPC/WinUI-Modus
   ```python
   self.engine.synthesizer.speak("Ja, Sir?")
   ```

### Was du konkret tun musst

**Schritt 1: Bestätigungston als WAV/MP3 erstellen**
Lege eine kurze Audiodatei ab, z.B. `jarvis/resources/sounds/confirmation.wav`. Ein kurzer aufsteigender Zweiklang (z.B. 200ms) passt zum JARVIS-Charakter.

**Schritt 2: Abspielfunktion zum Synthesizer hinzufügen**
In `jarvis/voice/synthesizer.py` (die Hauptklasse `SpeechSynthesizer`) eine neue Methode ergänzen, die den Ton direkt über `pygame.mixer` abspielt — pygame ist dort bereits importiert und initialisiert:

```python
def play_confirmation_sound(self) -> None:
    """Spielt einen kurzen Bestätigungston ab."""
    sound_path = Path(__file__).parent.parent / "resources" / "sounds" / "confirmation.wav"
    if sound_path.exists() and self._mixer_ready:
        sound = pygame.mixer.Sound(str(sound_path))
        sound.play()
        while sound.get_length() > 0 and pygame.mixer.get_busy():
            time.sleep(0.05)
```

Wichtig: `pygame.mixer.Sound` statt `pygame.mixer.music` verwenden, damit es nicht mit der TTS-Wiedergabe kollidiert (music kann nur einen Track gleichzeitig).

**Schritt 3: Alle 4 Stellen ersetzen**
Ersetze jeden `speak("Ja, Sir?")`-Aufruf durch `play_confirmation_sound()`:

- `engine.py`: `self.synthesizer.play_confirmation_sound()`
- `voice_service.py`: `self._synthesizer.play_confirmation_sound()`
- `service_mediator.py`: Hier muss der `QMetaObject.invokeMethod`-Aufruf angepasst werden — statt `speak` mit dem Text "Ja, Sir?" die neue Methode aufrufen
- `server.py`: `self.engine.synthesizer.play_confirmation_sound()`

### Warum diese Architektur

- Die Methode gehört auf den **Synthesizer**, weil der bereits die Audio-Ausgabe (pygame mixer) verwaltet und weiß, ob das Audiosystem bereit ist.
- `pygame.mixer.Sound` (nicht `music`) ist richtig, weil der Bestätigungston kurz ist und `music` für die längere TTS-Ausgabe reserviert bleiben soll.
- Alle 4 Stellen müssen geändert werden, weil JARVIS 4 verschiedene Launch-Modi hat, die jeweils ihre eigene Voice-Pipeline-Implementierung besitzen.
