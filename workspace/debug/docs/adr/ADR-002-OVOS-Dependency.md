# ADR-002: OVOS-Abhängigkeit

**Status:** Akzeptiert  
**Datum:** 2025-07-13  
**Entscheider:** Projektleitung  

## Kontext

TARNO nutzt 13 OVOS-Packages (OpenVoiceOS), die aber nur im `--no-gui` Launch-Modus aktiv verwendet werden:

```
ovos_core, ovos_messagebus, ovos_bus_client, ovos_config,
ovos_plugin_manager, ovos_persona, ovos-number-parser,
ovos_openai_plugin, ovos_solver_failure_plugin,
ovos-solver-yes-no-plugin, ovos-spec-tools, ovos-utils, ovos-workshop
```

### Auswirkungen

| Aspekt | Messwert |
|---|---|
| Installer-Größe | 710 MB (Gesamt-Package) |
| OVOS-Anteil (geschätzt) | ~80-120 MB (OVOS + transitive Deps) |
| Code-Stellen die OVOS nutzen | `tarno/core/ovos_engine.py`, `tarno/core/agent_service.py` |
| Launch-Modi mit OVOS | nur `--no-gui` |
| Aktive Entwicklung | OVOS wird nicht aktiv für TARNO weiterentwickelt |

### Problem

- OVOS-Packages erhöhen die Installer-Größe signifikant
- `ovos_config` wird bei jedem Import geladen, auch wenn OVOS nicht genutzt wird (XDG-Pfade)
- OVOS-Abhängigkeiten ziehen weitere transitive Dependencies rein
- Der `--no-gui` Modus wird nicht aktiv genutzt oder getestet

## Optionen

### Option A: Sofort entfernen

- OVOS-Code löschen, Dependencies entfernen
- **Risiko:** `--no-gui` Modus bricht sofort
- **Vorteil:** Sofortige Größenreduktion

### Option B: Isolieren und optional machen — EMPFOHLEN

- OVOS-Imports hinter `try/except ImportError` oder Feature-Flag setzen
- OVOS aus `requirements.txt` und `tarno.spec` entfernen
- `--no-gui` Modus nur verfügbar wenn OVOS installiert ist
- PySide6 ebenfalls aus dem Bundle entfernen (Legacy-UI)

### Option C: Beibehalten

- Keine Änderung
- **Risiko:** Installer bleibt bei 710+ MB

## Entscheidung

**Option B: Isolieren und optional machen.**

### Umsetzungsschritte

1. `tarno/core/ovos_engine.py` und `tarno/core/agent_service.py` bekommen Lazy-Imports
2. `__main__.py` fängt `ImportError` für `--no-gui` ab und gibt hilfreiche Fehlermeldung
3. OVOS-Packages aus `requirements.txt` in eigene `requirements-ovos.txt` verschieben
4. OVOS aus `tarno.spec` (PyInstaller) entfernen
5. PySide6 aus `tarno.spec` entfernen (Legacy-UI wird über WinUI bedient)

### Erwartete Größenreduktion

| Component | Geschätzt |
|---|---|
| PySide6 | -92 MB |
| OVOS-Stack | -80 MB |
| scipy (OVOS-Dep) | -66 MB |
| sklearn (OVOS-Dep) | -12 MB |
| **Gesamt** | **~250 MB** |

**Neue Installer-Größe:** ~460 MB → ~200 MB nach Kompression

## Konsequenzen

- `--no-gui` Modus erfordert `pip install -r requirements-ovos.txt`
- `--legacy-ui` Modus erfordert `pip install PySide6`
- Standard-Modus (WinUI) funktioniert ohne beides
- Dokumentation muss aktualisiert werden
