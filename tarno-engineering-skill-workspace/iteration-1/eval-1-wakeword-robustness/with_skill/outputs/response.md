Gute Frage! Ich hab mir den Wake-Word-Code und die Konfiguration angeschaut. Hier ist die Analyse und mein Vorschlag:

## Aktueller Stand

Du nutzt laut `config/default.yaml` das Modell `hey_jarvis` (openWakeWord-Backend). Die relevanten Parameter sind:

| Parameter | Aktuell | Datei |
|-----------|---------|-------|
| `threshold` | 0.5 | `config/default.yaml` Zeile 18 |
| `patience` | 3 | `config/default.yaml` Zeile 20 |
| `debounce_time` | 1.0 | `config/default.yaml` Zeile 21 |

Die Logik in `jarvis/voice/wakeword.py` (Zeile 134-149) funktioniert so: Jeder Audio-Frame wird durch openWakeWord gejagt und liefert einen Score (0.0-1.0). Nur wenn der Score **mindestens `patience` Frames in Folge** ueber dem `threshold` liegt, wird das Wake Word als erkannt gewertet.

## Das Problem bei Hintergrundgeraeuschen

Mit `patience=3` und `threshold=0.5` ist die Erkennung relativ streng: Drei aufeinanderfolgende Frames muessen alle ueber 0.5 scoren. Bei Hintergrundgeraeuschen kann es passieren, dass ein einzelner verrauschter Frame den Score kurzzeitig unter den Threshold drueckt -- und dann wird der `_consecutive`-Zaehler auf 0 zurueckgesetzt (Zeile 138). Das erklaert, warum die Erkennung bei Laerm unzuverlaessig wird.

## Empfohlene Aenderungen

### 1. Threshold senken (einfachste Massnahme)

**Datei:** `config/default.yaml`, Zeile 18
**Aenderung:** `threshold: 0.5` auf `threshold: 0.3` senken

Das erlaubt auch leicht verrauschte Frames, die trotzdem "Hey Jarvis" enthalten. Werte unter 0.2 wuerde ich vermeiden, da dann False Positives zunehmen.

Alternativ ueber Umgebungsvariable ohne Datei-Aenderung testbar:
```
set JARVIS_WAKEWORD_THRESHOLD=0.3
```
(Definiert in `jarvis/core/config.py`, Zeile 204)

### 2. Patience reduzieren

**Datei:** `config/default.yaml`, Zeile 20
**Aenderung:** `patience: 3` auf `patience: 2` reduzieren

Statt 3 aufeinanderfolgende Treffer reichen 2. Das macht die Erkennung deutlich robuster gegen einzelne "Aussetzer-Frames" bei Laerm.

### 3. (Optional, fortgeschritten) Sliding-Window statt strikt konsekutiv

Das aktuelle System in `jarvis/voice/wakeword.py` Zeile 138 setzt den Zaehler bei einem einzigen Frame unter Threshold sofort auf 0 zurueck:
```python
self._consecutive = self._consecutive + 1 if score >= self._threshold else 0
```

Eine robustere Alternative waere ein Sliding-Window-Ansatz: z.B. "mindestens 2 von 4 Frames ueber Threshold" statt "3 von 3 konsekutiv". Das wuerde in `_process_openwakeword()` eine kleine deque erfordern, aehnlich wie der Porcupine-Backend-Buffer es schon macht. Beispiel-Logik:

```python
# In __init__: self._score_window = deque(maxlen=5)
# In _process_openwakeword:
self._score_window.append(score >= self._threshold)
hits = sum(self._score_window)
if hits < self._patience:
    return False
```

Das waere die sauberste Loesung, erfordert aber eine Code-Aenderung in `jarvis/voice/wakeword.py`.

## Empfehlung

Starte mit Option 1 + 2 (nur Config-Aenderung, kein Code):

```yaml
wakeword:
  threshold: 0.3
  patience: 2
  debounce_time: 1.0
```

Teste damit in einer lauten Umgebung. Wenn zu viele False Positives kommen, Threshold auf 0.35 erhoehen. Wenn es immer noch nicht zuverlaessig genug ist, lohnt sich Option 3 (Sliding Window).

## Betroffene Komponenten

Die Aenderung wirkt sich auf alle drei Voice-Pipeline-Implementierungen gleichermassen aus (JarvisEngine, ServiceMediator, VoiceController), da alle denselben `WakeWordDetector` mit derselben Config nutzen. Keine Seiteneffekte auf STT, TTS oder LLM.
