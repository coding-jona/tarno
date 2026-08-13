# ADR-001: UI-Framework-Wahl

**Status:** Akzeptiert  
**Datum:** 2025-07-13  
**Entscheider:** Projektleitung  

## Kontext

TARNO benötigt ein UI-Framework, das folgende Anforderungen erfüllt:
- Liquid-Glass-Design mit Transparenz, Lichtbrechung, Glow-Effekten
- Flüssige Animationen (60 FPS) und natürliches Motion Design
- Native Windows-Integration (Taskbar, Notifications, System Tray)
- GPU-beschleunigte Rendering-Pipeline
- Langfristige Wartbarkeit und Zukunftssicherheit
- Professionelle Produktqualität (kein "Dev-Tool"-Look)

Aktuell existieren zwei UI-Stacks parallel:
- **WinUI 3** (C#/XAML) — aktives Frontend, verbunden via gRPC
- **PySide6** (Python/Qt) — Legacy-UI, wird nicht mehr aktiv entwickelt

## Bewertung der Optionen

### Option A: WinUI 3 (C#/XAML) — EMPFOHLEN

| Kriterium | Bewertung |
|---|---|
| **Liquid Glass** | ★★★★★ Native Mica/Acrylic Materialien. Composition-API bietet `PointLight`, `AmbientLight`, `SceneLightingEffect` für dynamische Glaseffekte. `AcrylicBrush` mit Custom-Tint/Luminosity. |
| **Animationen** | ★★★★★ Composition Animations (Spring, Expression, KeyFrame) laufen auf dem DWM-Thread, unabhängig vom UI-Thread. Connected Animations für Page-Transitions. |
| **GPU** | ★★★★★ DirectX-basiertes Rendering via Windows.UI.Composition. Hardware-beschleunigt out-of-the-box. |
| **Native Integration** | ★★★★★ Direkte Windows-API-Zugriffe. Taskbar Progress, Jump Lists, Toast Notifications nativ. |
| **Performance** | ★★★★★ ~127 MB für UI-Package. Kein Chromium-Overhead. Startup < 1s. |
| **Wartbarkeit** | ★★★★☆ C# + XAML ist typsicher und gut tooled. MVVM mit CommunityToolkit. Nachteil: separater Tech-Stack von Python-Backend. |
| **Zukunft** | ★★★★☆ Microsoft-backed, aktive Entwicklung (WindowsAppSDK 1.7). Windows-exklusiv. |

**Vorteile:**
- Mica/Acrylic sind echte Glasmaterialien, keine CSS-Hacks
- Composition-API ermöglicht Custom-Effekte die über Standard-Controls hinausgehen
- Self-Contained Deployment (kein separates Runtime-Install nötig dank `WindowsAppSDKSelfContained`)
- WebView2 als Escape-Hatch für komplexe Visualisierungen (z.B. Orb-Animation via WebGL)
- gRPC-Bridge zum Python-Backend existiert bereits und ist stabil

**Nachteile:**
- Windows-exklusiv (kein Linux/macOS)
- Composition-API ist schlecht dokumentiert
- XAML-Designer-Support in VS Code eingeschränkt

### Option B: Electron + React

| Kriterium | Bewertung |
|---|---|
| **Liquid Glass** | ★★★★☆ CSS `backdrop-filter`, WebGL-Shader, Three.js für 3D-Effekte. Sehr flexibel, aber kein echtes OS-Glasmaterial. |
| **Animationen** | ★★★★★ Framer Motion, GSAP, CSS Transitions. Riesiges Ökosystem. |
| **GPU** | ★★★☆☆ WebGL/WebGPU verfügbar, aber Chromium GC-Pausen können Jank verursachen. |
| **Native Integration** | ★★★☆☆ Über Node.js/Electron-APIs möglich, aber nicht nativ. |
| **Performance** | ★★☆☆☆ 150-300 MB RAM Baseline durch Chromium. Startup 2-4s. |
| **Wartbarkeit** | ★★★★☆ Web-Stack, großes Talentpool. Aber: npm-Dependency-Hölle. |
| **Zukunft** | ★★★★★ Cross-Platform, riesige Community. |

### Option C: Tauri + React

| Kriterium | Bewertung |
|---|---|
| **Liquid Glass** | ★★★★☆ Wie Electron, plus Rust-Backend für Custom-Effekte. |
| **Animationen** | ★★★★★ Gleich wie Electron (Web-Frontend). |
| **GPU** | ★★★★☆ WebView2 auf Windows (Edge), besser als Electron. |
| **Native Integration** | ★★★★☆ Rust-Bridge für native APIs. |
| **Performance** | ★★★★☆ ~30 MB RAM Baseline. Kein Chromium bundled (nutzt System-WebView). |
| **Wartbarkeit** | ★★★☆☆ Rust + TypeScript + Python = 3 Sprachen. |
| **Zukunft** | ★★★★☆ Aktiv, aber jüngeres Projekt. |

### Option D: PySide6 (Status Quo Legacy)

| Kriterium | Bewertung |
|---|---|
| **Liquid Glass** | ★★☆☆☆ QGraphicsEffect für Blur, aber keine echte Transparenz. Kein OS-Glasmaterial. |
| **Animationen** | ★★☆☆☆ QPropertyAnimation ist funktional, aber primitiv. Keine Spring-Physik. |
| **GPU** | ★★☆☆☆ OpenGL via QOpenGLWidget, aber Qt-Rendering ist primär CPU. |
| **Native Integration** | ★★★☆☆ Qt abstrahiert von Windows-APIs. |
| **Performance** | ★★★☆☆ 92 MB im PyInstaller-Bundle (PySide6-Ordner allein). |
| **Wartbarkeit** | ★★★★★ Gleiche Sprache wie Backend (Python). |
| **Zukunft** | ★★★☆☆ Qt-Lizenzkosten für kommerzielle Nutzung. |

## Entscheidung

**WinUI 3 (Option A)** wird als primäres UI-Framework bestätigt.

### Begründung

1. **Liquid Glass ist ein Kernziel.** WinUI 3 ist das einzige Framework mit nativen Glasmaterialien (Mica, Acrylic) und einer Composition-API für Custom-Effekte. Alle anderen Optionen simulieren Glass nur.

2. **Performance matters.** TARNO läuft dauerhaft im Hintergrund. 127 MB vs. 300+ MB (Electron) ist signifikant.

3. **Die Investition existiert bereits.** gRPC-Bridge, MVVM-Architektur, 6 Pages und Styles sind implementiert.

4. **Windows-Exklusivität ist akzeptabel.** TARNO ist ein Windows-Desktop-Produkt. Cross-Platform ist kein Ziel.

5. ~~WebView2 als Hybrid-Escape-Hatch~~ — **verworfen, siehe Update 2026-07-13 unten.**

## Konsequenzen

- PySide6-Legacy-UI (`tarno/ui/`) wird in Phase 2 als deprecated markiert
- PySide6-Abhängigkeit wird aus PyInstaller-Bundle entfernt (spart ~92 MB)
- Alle neuen UI-Features werden ausschließlich in WinUI 3 entwickelt
- Composition-API-Expertise muss aufgebaut werden (Dokumentation ist dünn)
- Der `--legacy-ui` Launch-Modus bleibt vorerst als Fallback erhalten

## Update 2026-07-13: WebView2-Hybrid-Strategie verworfen

Die ursprünglich hier empfohlene Hybrid-Strategie (WebView2-Panel für den Voice-Orb) wurde **in der Praxis getestet und als nicht funktionsfähig verworfen**:

- WebView2 wurde für den Voice-Orb implementiert (HTML/CSS/JS-Overlay, `HologramOverlayWebView`), navigierte erfolgreich (`EnsureCoreWebView2Async: OK`, `NavigationCompleted: IsSuccess=True`), rendert aber **visuell nichts** (grauer/schwarzer Block) in dieser WinUI3+Layered-Window-Umgebung — bestätigt per Diagnose-Testseite (roter Testhintergrund blieb unsichtbar).
- Root Cause vermutlich GPU/Compositor-Ebene, nicht durch CSS/C#-Änderungen behebbar (konsistent mit anderen in diesem Projekt beobachteten Rendering-Anomalien, z.B. `AcrylicBrush`-Crashes im XAML-Compiler).
- **Ersatzlösung:** Der Voice-Orb wurde vollständig auf reines XAML umgestellt (`Ellipse`-Elemente `OrbGlow`/`OrbCore` in `VoicePage.xaml`, gesteuert über `ThinkingViewModel`/`ThinkingState`). Das funktioniert zuverlässig und ohne die WebView2-Abhängigkeit.
- `Microsoft.Web.WebView2`-NuGet-Paket ist weiterhin im `.csproj` referenziert (Altlast), wird aber für den Orb nicht mehr genutzt.

**Konsequenz für künftige Sessions/Agenten:** WebView2 nicht erneut als Lösung für Visualisierungen in diesem Projekt vorschlagen, ohne vorher zu prüfen, ob sich die Umgebungsbedingung geändert hat (z.B. anderes Windows-Build, andere WindowsAppSDK-Version). Reines XAML (Composition-API, `Ellipse`/`Shape`-Elemente, Storyboards) ist der bewährte Pfad für Custom-Visualisierungen in diesem Projekt.
