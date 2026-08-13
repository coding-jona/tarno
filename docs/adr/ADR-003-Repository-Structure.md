# ADR-003: Repository-Struktur

**Status:** Akzeptiert  
**Datum:** 2025-07-13  
**Entscheider:** Projektleitung  

## Kontext

JARVIS besteht aus zwei technisch getrennten Komponenten:
- **Python-Backend** (`jarvis/`, `config/`, `tests/`)
- **WinUI-Frontend** (`src/JARVIS.UI/`)

Beide liegen aktuell im selben Repository (`openWakeWord-0.6.0/`), das ursprünglich ein Fork von openWakeWord war.

### Probleme

1. **Repository-Name:** `openWakeWord-0.6.0` spiegelt nicht wider, dass dies das JARVIS-Projekt ist
2. **Pfad-Kopplung:** `jarvis.spec` referenziert relative Pfade zu `src/JARVIS.UI/`
3. **Build-Kopplung:** Installer baut Python-Backend (PyInstaller) und WinUI (.NET) in einem Schritt
4. **Proto-Sharing:** `jarvis/grpc/jarvis.proto` wird von beiden Seiten referenziert

## Optionen

### Option A: Mono-Repo beibehalten — EMPFOHLEN

- Beide Komponenten bleiben im selben Repository
- Repository umbenennen in `jarvis` (oder neues Repo erstellen, Code migrieren)
- Verzeichnisstruktur aufräumen

### Option B: Multi-Repo

- `jarvis-backend` (Python)
- `jarvis-ui` (WinUI 3)
- Shared: `jarvis.proto` als Git-Submodule oder Copy

## Entscheidung

**Option A: Mono-Repo beibehalten.**

### Begründung

1. **Proto-Sharing ist trivial** im Mono-Repo (ein Pfad), komplex im Multi-Repo
2. **Installer baut beides** — ein Build-Skript, ein Artefakt
3. **Ein-Entwickler-Projekt** — Multi-Repo erzeugt nur Overhead
4. **Atomic Changes** — gRPC-Änderungen betreffen immer beide Seiten gleichzeitig

### Empfohlene Verzeichnisstruktur (Ziel)

```
jarvis/                         (Repository-Root, umbenannt)
├── backend/                    Python-Code (ex jarvis/)
│   ├── core/
│   ├── ai/
│   ├── voice/
│   ├── grpc/
│   └── ...
├── frontend/                   WinUI 3 (ex src/JARVIS.UI/)
│   ├── Pages/
│   ├── Styles/
│   └── ...
├── proto/                      Shared Proto-Definitionen
│   └── jarvis.proto
├── config/
├── tests/
├── installer/
├── scripts/
├── docs/
│   └── adr/
├── requirements.txt
├── jarvis.spec
└── JARVIS_Installer.nsi
```

**Hinweis:** Diese Umstrukturierung ist NICHT für Phase 1 vorgesehen. Sie wird als separates Refactoring in einer späteren Phase durchgeführt, wenn alle Pfad-Referenzen systematisch aktualisiert werden können.

## Konsequenzen

- Kurzfristig: Keine Änderung an der Dateistruktur
- Mittelfristig: Repository umbenennen, Verzeichnisse reorganisieren
- Proto-Datei bleibt an einer Stelle, referenziert von beiden Build-Systemen
