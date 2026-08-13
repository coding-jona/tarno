# Liquid Glass — Recherche & Umsetzungsplan (2026-07-13)

Auslöser: Die Sidebar-"Liquid Glass"-Umsetzung (`GlassStyles.xaml`, reiner `AcrylicBrush` + linearer Gradient-Rand) entsprach nicht dem echten Apple-Design aus den bereits vorhandenen Referenz-Artefakten. Dieses Dokument verankert die Neuumsetzung in (1) den eigenen Referenz-Artefakten und (2) Apples dokumentierten Prinzipien, bevor wieder XAML geschrieben wird — siehe `.claude/skills/named-design-system-fidelity/SKILL.md`.

## 1. Apples dokumentierte Prinzipien (WWDC25 / iOS 26 HIG)

Quelle: [Apple Newsroom](https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/), [Apple Developer — Liquid Glass](https://developer.apple.com/documentation/TechnologyOverviews/liquid-glass), [createwithswift.com Analyse](https://www.createwithswift.com/liquid-glass-redefining-design-through-hierarchy-harmony-and-consistency/)

- **Translucentes Material**, das seine Umgebung **reflektiert und bricht** (refraction/lensing in Echtzeit), nicht nur verwischt.
- **Specular Highlights, die auf Bewegung reagieren** (Gerätebewegung auf iOS; Äquivalent auf Desktop: Zeiger-/Fensterposition).
- **Adaptive Schatten** statt fixer Schattenwerte.
- **Wichtigkeit wird über Transparenz-/Brechungs-Abstufung kommuniziert**, nicht (nur) über Farbe/Größe — d.h. wichtigere Elemente bekommen stärkere/andere Glas-Eigenschaften, nicht nur mehr Kontrast.
- macOS/iPadOS-Sidebars **brechen den Inhalt dahinter** und **reflektieren** Inhalt/Wallpaper der Umgebung — genau der Sidebar-Anwendungsfall, um den es hier geht.

Reines `backdrop-filter: blur()` (bzw. `AcrylicBrush` in WinUI) bildet nur den "verwischt"-Teil ab, nicht Reflexion, Lensing oder bewegungsreaktive Highlights. Das ist der Kern der Lücke im ersten Versuch.

## 2. Eigene Referenz-Artefakte (bereits vorhanden, jetzt ausgewertet)

Zwei Artefakte aus einer früheren Session (vor dem `/clear`) enthalten bereits funktionierenden CSS-Code, der Apples Prinzipien technisch näherungsweise umsetzt:

- [JARVIS Hologram Overlay — Mockup](https://claude.ai/code/artifact/3ed87f82-7742-414b-9013-57a9e1bb2937) (Orb-Fokus)
- [JARVIS Plan — Liquid Glass Preview](https://claude.ai/code/artifact/d7ea98e2-d72d-41ab-9d79-6fc8e1e9379d) (Sidebar-/Karten-Fokus, `.glass`-Primitive)

Konkrete Mechaniken aus dem `.glass`-Primitiv (Liquid-Glass-Preview-Artefakt):

```css
.glass {
  background: var(--glass);                          /* halbtransparentes Weiß/Dunkel */
  backdrop-filter: blur(22px) saturate(160%);         /* Blur + Sättigungs-Boost, nicht nur Blur */
  border: 1px solid var(--glass-edge-lo);
  border-top-color: var(--glass-edge-hi);             /* HELLERE Kante oben/links … */
  border-left-color: var(--glass-edge-hi);             /* … simuliert Lichtquelle von oben-links */
  box-shadow: var(--shadow), inset 0 1px 0 rgba(255,255,255,0.35); /* Außen-Schatten + Inset-Highlight-Linie */
  isolation: isolate;
  overflow: hidden;
}
.glass::before {
  /* bewegter Specular-Highlight, an --mx/--my (Zeigerposition) gekoppelt */
  background: radial-gradient(280px 280px at var(--mx,30%) var(--my,10%),
              rgba(255,255,255,0.55), transparent 60%);
}
```
JS koppelt `--mx`/`--my` an `mousemove` pro Karte — das ist die **bewegungsreaktive Specular-Highlight**-Entsprechung auf einem Gerät ohne Gyroskop.

Zusätzliche Mechaniken aus dem Orb-Mockup:
- **Rotierender Rim-Light-Saum** über `conic-gradient` + `mask-composite: exclude` + animiertes `@property --rim-angle` (Ring, der Licht an der gekrümmten Kante simuliert).
- **Farbige, unscharfe Hintergrund-„Blobs“** (`filter: blur(90–100px)`, langsam driftend), die im Hintergrund liegen — **ohne diese ist Glas-Blur unsichtbar**, weil nichts Farbiges zum Brechen da ist. Ein flacher/dunkler Hintergrund macht jeden Blur-Effekt bedeutungslos.
- Vollständig separate Light/Dark-Token-Sets (unterschiedliche Alpha-/Blur-Stärken je Theme, nicht nur Farbwechsel).
- `prefers-reduced-motion`-Handling für alle Animationen.

## 3. Lücken-Analyse: erster Sidebar-Versuch vs. Zielbild

| Mechanik | Apple-Prinzip | Referenz-Artefakt | Erster Sidebar-Versuch (`GlassStyles.xaml`) |
|---|---|---|---|
| Blur + Sättigung | Refraktion | ✅ `blur(22px) saturate(160%)` | ⚠️ nur `AcrylicBrush`-Standardblur, keine Sättigungsanhebung |
| Bewegungsreaktiver Specular-Highlight | ✅ Kernprinzip | ✅ `--mx`/`--my` radial-gradient | ❌ fehlt komplett |
| Asymmetrische Kanten-Highlights (Lichtquelle) | Reflexion | ✅ hell oben/links, dunkel unten/rechts | ❌ einheitlicher linearer Gradient-Rand |
| Inset-Highlight-Linie | Reflexion | ✅ `inset 0 1px 0 …` | ❌ fehlt |
| Farbiger, unscharfer Hintergrund hinter dem Glas | Grundvoraussetzung für sichtbare Refraktion | ✅ „Blobs“ | ❌ Sidebar liegt auf normalem `MicaBackdrop`/Fensterhintergrund ohne Farbschicht |
| Rotierender Rim-Light | Lensing an gekrümmten Kanten | ✅ (Orb) | n/a (Sidebar ist eckig, aber Prinzip fehlt generell) |
| Abstufung nach Wichtigkeit | HIG-Vorgabe | teilweise (`glass` vs `glass-strong`) | ❌ ein einziger Brush für alles |

## 4. WinUI-3-Technikoptionen (Recherche-Ergebnis)

Quelle: [Microsoft Learn — Custom effects (Win2D)](https://learn.microsoft.com/en-us/windows/apps/develop/win2d/custom-effects), [Visual layer overview](https://learn.microsoft.com/en-us/windows/apps/windows-app-sdk/composition), [PixelShaderEffect](https://microsoft.github.io/Win2D/WinUI3/html/T_Microsoft_Graphics_Canvas_Effects_PixelShaderEffect.htm)

**Option A — Composition-Layer-Näherung (kein Win2D nötig):**
- `AcrylicBrush` bleibt Basis für Blur+Tint (bereits vorhanden).
- Bewegungsreaktiver Specular-Highlight: `SpriteVisual` + `CompositionRadialGradientBrush`, dessen Zentrum per `PointerMoved`-Handler animiert wird (`ExpressionAnimation` an Pointer-Position gekoppelt) — direktes Äquivalent zum `--mx`/`--my`-Trick aus dem Referenz-CSS.
- Asymmetrische Kanten-Highlights: zwei überlagerte `LinearGradientBrush`-Ränder (hell oben-links → transparent unten-rechts) statt eines einzelnen Rand-Brushs.
- Inset-Highlight: zusätzliche 1px `Border` mit `RenderTransform`, innen liegend.
- Farbiger Hintergrund: eigene `Blobs`-Canvas-/Grid-Ebene hinter der Sidebar mit 2-3 weichen, radialen, langsam animierten Farbflächen (Cyan/Violett/Teal passend zu `Colors.xaml`).
- **Kosten:** gering (Composition-API läuft bereits GPU-komposit, kein Extra-Shader-Compile), passt zum CPU-first-Grundsatz des Projekts, da die GPU-Last minimal bleibt.

**Option B — Echter Pixel-Shader (Win2D/ComputeSharp):**
- `PixelShaderEffect` mit eigenem HLSL/ComputeSharp-Shader für echtes Lensing (Verzerrung des Hintergrunds, nicht nur Blur+Tint) und physikalisch korrektere Specular-Reflexion (`SpotSpecularEffect` als Ausgangspunkt).
- **Kosten:** deutlich höher — Shader-Kompilierung, zusätzliche GPU-Last im Idle-Zustand (Sidebar ist dauerhaft sichtbar), mehr Fehlerfläche (Shader-Kompatibilität über GPU-Generationen). Auf der AMD RX 6600 unter Windows (bereits als langsam für andere GPU-Workloads dokumentiert) ein Risiko für Dauerlast bei etwas, das ständig sichtbar ist.

**Empfehlung:** Option A für die Sidebar (und generell alle dauerhaft sichtbaren Flächen). Option B nur für den Orb später in Betracht ziehen, wo es um einen einzelnen, kleinen, zentralen Blickfang geht (geringere Fläche = geringere Dauerlast), und auch dort zuerst mit Composition-Näherung starten und nur bei tatsächlichem visuellem Bedarf auf Shader eskalieren.

## 5. Konkreter Umsetzungs-Fahrplan (Sidebar zuerst)

1. `Styles/Hologram.xaml`: Farbtoken für „Blobs“ ergänzen (an `Colors.xaml`-Cyan-Akzent angelehnt, 2-3 Farbflächen).
2. Neue `BlobBackground`-Ebene hinter der Sidebar (eigenes Control oder Grid-Layer), mit `CompositionRadialGradientBrush` + langsamer `Vector2KeyFrameAnimation` fürs Driften (Analog zu `@keyframes drift`).
3. `GlassStyles.xaml`: `LiquidGlassBrush` ersetzen/erweitern um asymmetrische Rand-Highlights + Inset-Linie (zwei Border-Layer statt einem).
4. Neues Attached-Behavior oder Code-Behind: Pointer-gekoppelter Specular-Highlight via `SpriteVisual`/`ExpressionAnimation`, wiederverwendbar für Sidebar und später Karten/Orb.
5. Visuelle Abstufung: `LiquidGlassBrush` (normal) vs. `LiquidGlassStrongBrush` (wichtigere Flächen) unterschiedlich stark parametrisieren (Blur/Opacity/Highlight-Intensität), nicht nur zwei benannte, aber gleich wirkende Brushes.
6. Test auf Performance im Idle-Zustand (CPU/GPU-Last über mehrere Minuten, gemäß Projekt-Konvention „CPU-first").
7. Danach — nicht vorher — Ausweitung auf weitere Flächen (Karten, künftiger Orb) mit demselben Baukasten.

## Quellen

- [Apple Newsroom — Apple introduces a delightful and elegant new software design](https://www.apple.com/newsroom/2025/06/apple-introduces-a-delightful-and-elegant-new-software-design/)
- [Apple Developer — Liquid Glass (Technology Overview)](https://developer.apple.com/documentation/TechnologyOverviews/liquid-glass)
- [createwithswift.com — Liquid Glass: Redefining design through Hierarchy, Harmony and Consistency](https://www.createwithswift.com/liquid-glass-redefining-design-through-hierarchy-harmony-and-consistency/)
- [Microsoft Learn — Implementing custom effects (Win2D)](https://learn.microsoft.com/en-us/windows/apps/develop/win2d/custom-effects)
- [Microsoft Learn — Visual layer overview](https://learn.microsoft.com/en-us/windows/apps/windows-app-sdk/composition)
- [Win2D — PixelShaderEffect Class](https://microsoft.github.io/Win2D/WinUI3/html/T_Microsoft_Graphics_Canvas_Effects_PixelShaderEffect.htm)
- [Win2D — SpotSpecularEffect Class](https://microsoft.github.io/Win2D/WinUI2/html/T_Microsoft_Graphics_Canvas_Effects_SpotSpecularEffect.htm)
- Eigene Referenz-Artefakte: [Hologram Overlay Mockup](https://claude.ai/code/artifact/3ed87f82-7742-414b-9013-57a9e1bb2937), [Liquid Glass Preview](https://claude.ai/code/artifact/d7ea98e2-d72d-41ab-9d79-6fc8e1e9379d)
