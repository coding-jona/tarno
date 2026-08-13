# TARNO Installer-Zwischenergebnis – BuildMC-Vergleich & Plan

Tauri/React wird ausgeschlossen (Performance-/RAM-Probleme in BuildMC). Das aktuelle PySide6-GUI wird als schnellstes, funktionsfähiges Zwischenergebnis gepackt, damit das Design live bewertet werden kann.

## Analyse BuildMC

- **BuildMC Launcher**: Tauri v2 + React + TypeScript + TailwindCSS + Framer Motion + Lucide Icons; Rust-Backend; MSI/NSIS via Tauri.
- **BuildMC AI Desktop**: Ebenfalls Tauri + React + Tailwind + Lucide; Vite-Build.
- **Gemeinsamer Nenner**: Web-UI in einem nativen WebView-Wrapper, verpackt durch Tauri. Damit wurde der XamlCompiler-Fehler von WinUI 3 umgangen.

## Aktueller Stand TARNO

- **WinUI-3-Projekt** (`src/TARNO.UI`): Bauen scheitert mit `XamlCompiler.exe` Exit Code 1 ohne sichtbare Fehlermeldung. Lösung erfordert weitere Toolchain-Diagnose (VS2022, SDK, XAML-Reduktion) oder einen Technologiewechsel.
- **PySide6-GUI** (`tarno/app.py`, `tarno/gui/`): Funktioniert, hat bereits ein dunkles BuildMC-artiges Design, ist der aktuelle „live“-Zustand.
- **gRPC-Backend**: `tarno/grpc/server.py` mit Mock-Engine läuft; war für die WinUI-3-Anbindung gedacht.
- **Vorhandener Installer**: PyInstaller + NSIS, aber für `tarno_ai_master.py` (alte Konsolen-/Voice-Version) und nicht für die neue GUI.

## Empfohlene Strategie

Ein sofort erstellbarer **`.exe`-Installer** für das aktuelle PySide6-GUI, damit das Design live betrachtet werden kann. WinUI 3 bleibt als separates Architekturziel erhalten, wird aber nicht blockierend.

## Schritte

1. **PyInstaller-Spec anpassen**
   - Einstiegspunkt: `tarno/app.py` bzw. `python -m tarno` (`tarno/__main__.py`)
   - `hiddenimports` ergänzen für `PySide6`, `tarno.gui`, `tarno.core`, `tarno.ai`, `tarno.desktop`, `tarno.voice`, etc.
   - Daten (YAML-Configs, ggf. Wake-Word-Modelle) als `datas` einbinden.

2. **Build & Smoke-Test**
   - `pyinstaller` ausführen, EXE starten, prüfen ob GUI erscheint.
   - Konsolen-Fehler und fehlende Module beheben.

3. **NSIS-Installer aktualisieren**
   - `TARNO_Installer.nsi` und `build_tarno_installer.py` auf das neue Dist-Verzeichnis der GUI anpassen.
   - Shortcuts auf das GUI-EXE setzen, nicht auf `tarno_ai_master.exe`.

4. **WinUI-3-Entscheidung nach Review**
   - Sobald der Installer getestet ist und Sie das Design bewertet haben, entscheiden: WinUI-3-Toolchain weiterdebuggen oder PySide6-GUI als Produkt-UI ausbauen.

## Entscheidung

Sofortigen **PySide6-GUI-Installer** bauen, um das aktuelle Design live sichtbar zu machen.
