# TARNO WinUI 3 – XamlCompiler-Debugging-Plan

Der WinUI-3-Build in `src/TARNO.UI` scheitert mit `XamlCompiler.exe` Exit Code 1 ohne sichtbare Fehlermeldung; das Python-gRPC-Backend läuft bereits stabil im Mock-Modus.

## Ziel
WinUI-3-Projekt erfolgreich bauen und starten, End-to-End mit dem Python-Backend verbinden.

## Schritte

1. **Diagnoseumgebung aufbauen**
   - Visual Studio 2022 Community installieren (Workload: `.NET Desktop Development` + `Windows application development` + optionale C++-Tools für Windows App SDK).
   - Alternativ, falls VS zu groß ist: Visual Studio Build Tools 2022 mit denselben Workloads.

2. **Problem isolieren**
   - Ein minimales, neues WinUI-3-Projekt (manuell oder per Template) bauen, um sicherzustellen, dass Toolchain grundsätzlich funktioniert.
   - Dann `TARNO.UI` schrittweise reduzieren:
     a. Alle XAML-Dateien außer `App.xaml` und `MainWindow.xaml` entfernen (nur ein leeres Fenster).
     b. Bei Erfolg `MainWindow.xaml` vereinfachen, dann Styles, dann Pages, dann Controls Stück für Stück wieder hinzufügen.

3. **Bekannte Verdachtspunkte prüfen**
   - `WindowsAppSDK`-Version ggf. auf 1.6.x aktualisieren.
   - `Microsoft.Windows.SDK.BuildTools` prüfen.
   - `ms-appx:///` ResourceDictionary-Quellen ggf. auf relative Pfade ändern.
   - `SelfContained`-Flag zurücksetzen, sobald der Build grundsätzlich funktioniert.
   - Eventuelle `CommunityToolkit.Mvvm`- oder `Grpc.Tools`-Konflikte ausschließen.

4. **Build & Run**
   - `dotnet build TARNO.UI.csproj -c Debug -p:Platform=x64` erfolgreich durchführen.
   - `dotnet run` ausführen, prüfen dass MainWindow erscheint.

5. **End-to-End-Test**
   - Python-Backend im Mock-Modus starten: `python start_tarno_winui_backend.py --mock`.
   - WinUI-App starten und überprüfen, dass Chat-Nachrichten vom Backend empfangen werden.

## Risiken
- Visual Studio 2022 ist groß (~6–10 GB) und braucht Zeit.
- XamlCompiler-Silent-Fail kann auch durch ein fehlendes Windows-Update / SDK-Feature verursacht werden.

## Entscheidung erforderlich
Soll ich mit Schritt 1 beginnen (Visual Studio 2022/Build Tools installieren)?
