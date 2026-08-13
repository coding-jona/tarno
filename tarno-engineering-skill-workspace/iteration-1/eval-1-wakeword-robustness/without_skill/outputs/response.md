Das Problem liegt daran, dass dein Jarvis-Wakeword aktuell pvporcupine als Backend nutzt (weil `model_name: "jarvis"` in der Config steht). Porcupine hat einen eingebauten "jarvis"-Keyword-Detektor, dessen Empfindlichkeit ueber den `threshold`-Wert (als `sensitivities` an Porcupine uebergeben) gesteuert wird. Hier sind die konkreten Anpassungen, die du machen kannst:

---

## 1. Threshold senken (schnellster Fix)

**Datei:** `config/default.yaml`

Aendere den `threshold` von `0.5` auf einen niedrigeren Wert, z.B. `0.3` oder `0.35`:

```yaml
wakeword:
  threshold: 0.3
```

Bei pvporcupine ist `sensitivities` ein Wert zwischen 0 und 1. Niedrigere Werte bedeuten weniger Fehlerkennungen aber auch mehr verpasste Erkennungen. Hoehere Werte (naeher an 1.0) machen die Erkennung empfindlicher -- also robuster bei Hintergrundgeraeusch, aber mit mehr False Positives. Teste Werte zwischen 0.3 und 0.7, bis du den besten Kompromiss findest.

**Betroffener Code:** `jarvis/voice/wakeword.py`, Zeile 53-55:
```python
self._porcupine = pvporcupine.create(
    keywords=["jarvis"],
    sensitivities=[float(config.threshold)],
)
```

## 2. Patience reduzieren

**Datei:** `config/default.yaml`

Der `patience`-Wert ist aktuell `3`, aber fuer das Porcupine-Backend wird er im Code auf `1` hartcodiert (Zeile 43 in `wakeword.py`):

```python
if normalized in ("jarvis", "jarvis_v1"):
    self._backend = "porcupine"
    self._patience = 1
```

Das ist also bereits optimal -- eine einzelne Erkennung genuegt. Hier muss nichts geaendert werden.

## 3. Debounce-Time senken

**Datei:** `config/default.yaml`

Der Wert `debounce_time: 1.0` verhindert, dass innerhalb von einer Sekunde erneut getriggert wird. Wenn du mehrfach schnell hintereinander "Hey Jarvis" sagst und es nicht reagiert, kann das daran liegen. Fuer den Normalfall ist 1.0s aber angemessen.

## 4. Umgebungsgeraeusch-Kalibrierung verbessern

**Datei:** `jarvis/voice/recognizer.py`, Zeile 38

Die aktuelle Kalibrierungsdauer ist nur 0.5 Sekunden:
```python
self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
```

Erhoehe das auf 1.0 oder 2.0 Sekunden fuer bessere Kalibrierung bei Hintergrundlaerm:
```python
self._recognizer.adjust_for_ambient_noise(source, duration=1.5)
```

**Hinweis:** Das betrifft die STT-Erkennung nach dem Wake Word, nicht die Wake-Word-Erkennung selbst. Aber es hilft, wenn nach dem Wake-Word-Trigger die gesprochenen Befehle bei Laerm nicht erkannt werden.

## 5. openWakeWord mit Noise Suppression nutzen (fortgeschritten)

Falls du statt Porcupine das openWakeWord-Backend verwenden moechtest (z.B. mit einem anderen Modellnamen), bietet das Framework eine eingebaute Speex-Rauschunterdrueckung. Dafuer muesste `wakeword.py` angepasst werden:

**Datei:** `jarvis/voice/wakeword.py`, in `_init_openwakeword()` (Zeile 90):

```python
self._model = OWWModel(
    wakeword_models=[str(wakeword_path)],
    inference_framework=config.inference_framework,
    melspec_model_path=str(melspec_path),
    embedding_model_path=str(embedding_path),
    enable_speex_noise_suppression=True,  # <-- hinzufuegen
)
```

Zusaetzlich kann der VAD-Threshold gesetzt werden, um Vorhersagen zu filtern, die nicht mit menschlicher Sprache korrelieren:

```python
self._model = OWWModel(
    ...,
    enable_speex_noise_suppression=True,
    vad_threshold=0.5,
)
```

Das ist allerdings nur fuer das openWakeWord-Backend relevant, nicht fuer Porcupine.

## Empfohlene Sofortmassnahme

Aendere in `config/default.yaml` den Threshold auf `0.7` (empfindlicher):

```yaml
wakeword:
  threshold: 0.7
```

Teste damit. Wenn zu viele Fehlerkennungen auftreten, reduziere schrittweise (0.6, 0.5). Wenn es immer noch nicht zuverlaessig erkennt, geh auf 0.8. Der optimale Wert haengt von deiner Umgebung ab.
