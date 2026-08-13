# TARNO PySide6 GUI komplett als BuildMC AI Design-Clone

Die bestehende TARNO-Oberfläche wird komplett verworfen und als PySide6-Nachbau des BuildMC AI Desktop neu aufgebaut; Funktionalität der Seiten folgt in einer separaten Phase, wenn das Design steht.

## Entscheidungen

- **Akzentfarbe:** BuildMC AI Brand-Lila (`#8b5cf6` / `#7c3aed`) übernehmen.
- **Layout:** 240px Sidebar mit Brand-Header + Icon/Label-Navigation + Footer; Hauptbereich mit Page-Header und Card-Grid.
- **Seiten:** Dashboard, Chat, Voice, Tasks, Plugins, Memory, Browser, Models, Settings, Logs (an BuildMC AI angelehnt, aber TARNO-Funktionen).
- **Priorität:** Design zuerst; vollständige Seiten-Funktionalität und Menü-Interaktionen als Phase 2 nach dem Design-Review.

## Umsetzungsschritte

1. **Theme komplett umbauen**
   - BuildMC AI Farbpalette: `dark-900` #0f0f13, `dark-800` #18181b, `dark-700` #27272a, `dark-600` #3f3f46, `brand-500` #8b5cf6, `brand-600` #7c3aed.
   - Inter-Schriftart, 8px/12px Radien, Card-Styles, Button-Styles (btn-primary, btn-secondary, btn-danger), Input-Styles.

2. **Sidebar exakt nach BuildMC AI Layout.tsx**
   - Brand-Header: Titel „TARNO“ + Untertitel „AI Assistant“.
   - Navigationsliste mit Icon + Label + Active-State (lila Hintergrund, weiße Schrift).
   - Footer: Version + Plattform.

3. **Dashboard-Seite**
   - Seiten-Titel + Status-Indikator.
   - Stat-Card-Grid (Provider, Status, Tools, Memory, etc.).
   - Service-/Action-Cards mit lila Buttons.
   - System-Info- und Log-Cards.

4. **Chat-Seite**
   - Vollständiger Nachbau von BuildMC AI `Chat.tsx`: Nachrichten im Card-Container, User rechts (brand-600), Assistant links (dark-700), Input + Send-Button unten, „Thinking…“-Indikator.

5. **Weitere Seiten als Design-Platzhalter**
   - Voice, Tasks, Plugins, Memory, Browser, Models, Settings, Logs.
   - Jeweils mit echtem BuildMC-Layout (Cards, Überschriften, Tabellen, Formularfelder), aber ohne vollständige Backend-Anbindung.

6. **Main Window anpassen**
   - Sidebar + Content-Stack für alle 10 Seiten.
   - Kein zusätzlicher Titel-Bar mehr (wie aktuell); nur Sidebar + Hauptbereich wie BuildMC AI.

7. **Installer neu bauen**
   - PyInstaller + NSIS mit der neuen GUI.
   - Alte Version vor der Installation entfernen lassen.

8. **Phase 2 (nach Design-Review)**
   - Jede Seite mit echter Backend-Funktionalität verbinden.
   - Menü-Navigation fehlerfrei und ohne Abstürze sicherstellen (wird mit Cloud abgestimmt).

## Ergebnis

Ein visuell nahezu identischer BuildMC AI Clone für TARNO, auf dem später die echten TARNO-Funktionen aufgebaut werden.
