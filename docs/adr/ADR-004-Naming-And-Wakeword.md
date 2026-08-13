# ADR-004: Rebranding-Kandidat "Kev" & lokales CPU-only Wake-Word-Training

**Status:** Entschieden — Name: **"Tarno"** (2026-07-13). Umsetzung (Umfang: sichtbare Ebene vs. auch Code-Identifier) noch offen, bewusst zurückgestellt wegen Usage-Limit. Nächster Schritt bei Fortsetzung: Umfang klären, dann Umsetzungsplan.
**Datum:** 2026-07-13
**Entscheider:** Projektleitung (ausstehend)

## Kontext

Der Name "JARVIS" ist markenrechtlich riskant (starke Assoziation mit
Marvel/Iron Man). Der Nutzer hat "Kev" als Kandidaten für einen eigenständigen
Rufnamen vorgeschlagen und um Analyse von Markenfähigkeit, Alternativen,
technischer Machbarkeit eines lokalen Wake-Words und Integrationsaufwand
gebeten. Dies ist eine reine Analyse — noch keine Umsetzung.

---

## 1. Markenfähigkeit von "Kev"

**Rechtlich (markenrechtliche Stärke):** "Kev" ist als Fantasiename für ein
KI-Produkt tendenziell *arbiträr* (kein beschreibender Bezug zur Funktion),
was grundsätzlich eine starke Markenkategorie ist — vergleichbar mit "Claude"
für einen KI-Assistenten. Das ist die gute Nachricht.

**Kollisionsrisiko (Recherche 2026-07-13):**

| Fund | Bereich | Risiko |
|---|---|---|
| **Kev.AI** (Otter Property Management) | Personalisierter KI-Chatbot, trainiert auf einer realen Person "Kevin" | **Mittel-hoch** — exakt gleicher Produktbereich (KI-Assistent), Domain `kev.ai` ist bereits registriert ("KEV.AI Lab", im Aufbau) |
| Keine USPTO-Eintragung gefunden | — | Keine formale Registrierung bekannt, aber das ersetzt keine anwaltliche Volltextrecherche |

**Einschätzung:** "Kev" ist *nicht* eindeutig frei. Die Domain `kev.ai` ist
weg, und es existiert bereits ein Produkt im selben Marktsegment (persönlicher
KI-Assistent) mit exakt diesem Namen. Das schließt "Kev" nicht zwingend aus
(unterschiedliche Rechtsräume, kein eingetragenes Markenrecht gefunden), aber
es ist ein reales Kollisionsrisiko, kein sauberer Neustart. Vor einer
verbindlichen Entscheidung: professionelle Markenrecherche (z. B. DPMA/EUIPO
für Deutschland/EU, nicht nur USPTO) und Domain-Check für `.de`/`.com`/`.ai`.

## 2. Alternativen

| Name | Befund | Risiko |
|---|---|---|
| **Kevo** | Kwikset **Kevo** ist eine bekannte Smart-Lock-Marke (Bluetooth-Türschloss, App erst Nov. 2025 abgeschaltet, Marke aber weiter präsent, Amazon/Home-Depot-Listings) | **Hoch** — genau im Smart-Home-Adjazenzbereich, Verwechslungsgefahr |
| **Kivo** | **Kivo.ai** existiert bereits mehrfach: KI-Agenten für HR/CRM/Business-Automation, plus eine separate "KIVO"-Companion-App (Google Play) | **Hoch** — mehrere aktive Wettbewerber im KI-Assistenten-Raum, Domain weg |
| **Kyro** | **Kyro** existiert als Fitness-Coaching-KI-App und als Projektmanagement-Tool (beide auf Google Play/als eigene App) | **Hoch** — ebenfalls KI-Assistenten-Kategorie, Domain/App-Name weg |

**Fazit Alternativen:** Alle drei vorgeschlagenen Ausweichnamen sind stärker
belastet als "Kev" selbst — vor allem Kevo (physisches Smart-Home-Produkt,
großer Hersteller) und Kivo (mehrere aktive KI-SaaS-Produkte).

**Eigene Vorschläge zur Erweiterung des Kandidatenfelds** (kurz, nicht
recherchiert — nur als Ausgangspunkt für eine spätere Runde):
- Namen mit Doppelkonsonant/Umlaut-Variante, die auf Deutsch *und* Englisch
  sauber bleiben und seltener kollidieren, z. B. **"Revo"**, **"Nemo"**
  (Achtung: Filmassoziation), **"Talo"**, **"Bo"** (sehr kurz, ggf. zu
  generisch für Wake-Word-Erkennung — siehe Abschnitt 3).
- Personennamen-Charakter beibehalten, aber ungewöhnlicher: **"Fenn"**,
  **"Rook"**.
- Diese Liste ersetzt keine Recherche — jeder Kandidat braucht dieselbe
  Domain-/Marken-Prüfung wie oben für Kev/Kevo/Kivo/Kyro, bevor er ernsthaft
  in Betracht gezogen wird.

## 3. Technische Anforderungen an ein Wake-Word (unabhängig vom Namen)

Kurze Wörter mit wenigen unterscheidbaren Phonemen (z. B. "Bo", "Kev") haben
tendenziell **höhere False-Accept-Raten** als längere Phrasen ("Hey Jarvis",
"Hey Mycroft") — das ist ein bekannter Trade-off in der Wake-Word-Literatur
und auch im openWakeWord-README dokumentiert. "Kev" (1 Silbe, klarer
K-E-V-Kontrast) ist akustisch besser als z. B. "Bo", aber schwächer
unterscheidbar als eine Zwei-Wort-Phrase. Empfehlung: beim Training bewusst
False-Accept-Rate gegen reale Alltagssprache testen (siehe Abschnitt 4),
nicht nur gegen synthetische Negativbeispiele.

## 4. Lokales CPU-only Wake-Word-Training — technische Machbarkeit

**Wichtiger Befund:** Dieses Repository enthält bereits das vollständige
openWakeWord-Trainings-Toolkit im Unterordner
`openWakeWord-0.6.0/openWakeWord-0.6.0/`:

```
notebooks/automatic_model_training.ipynb   ← empfohlener Weg (auch als Colab)
notebooks/training_models.ipynb            ← Tutorial/Grundlagen
docs/synthetic_data_generation.md
```

Das ist exakt das, was für "Kev" gebraucht wird, und passt **1:1** zur
bestehenden Architektur — `jarvis/voice/wakeword.py` lädt bereits
openWakeWord-ONNX-Modelle CPU-only, ohne Cloud-Abhängigkeit (siehe
`_init_openwakeword`).

### Pipeline (laut openWakeWord-README + Notebook)

1. **Synthetische Trainingsdaten generieren** — Text-to-Speech erzeugt
   tausende Varianten von "Kev" (verschiedene synthetische Stimmen, Tonhöhen,
   Sprechgeschwindigkeiten). **Kein manuelles Sprachdaten-Sammeln nötig** —
   das ist der zentrale Vorteil von openWakeWord gegenüber klassischen
   Ansätzen. Positivbeispiele: "Kev"-Varianten. Negativbeispiele: allgemeine
   Sprache/Hintergrundgeräusche (bereits als Datensätze im Projekt-Ökosystem
   verfügbar, siehe `docs/synthetic_data_generation.md`).
2. **Training auf gefrorenem Feature-Extractor** — Ein kleiner Klassifikator
   wird auf Embeddings eines vortrainierten, eingefrorenen Google-Modells
   trainiert (das eigentliche Wake-Word-Modell ist klein — deshalb
   CPU-tauglich). Laut README: Basis-Modell in **unter 1 Stunde** trainierbar.
3. **Export als ONNX** — direkt kompatibel mit dem bestehenden
   `OWWModel(wakeword_models=[...])`-Aufruf in `wakeword.py`.
4. **Lokale Echtzeit-Inferenz** — bereits produktiv im Projekt (siehe
   `hey_jarvis_v0.1.onnx` als aktuelles Beispiel).

### Vergleich der drei genannten Optionen

| Option | CPU-only | Keine Cloud | Aufwand | Passt zur Architektur |
|---|---|---|---|---|
| **openWakeWord (custom)** | ✅ | ✅ | **Niedrig** — Tooling bereits vorhanden | ✅ direkt, `_OWW_MODEL_MAP` erweitern |
| **Porcupine Custom Keyword** | ✅ | ❌ (Cloud-Console + `PICOVOICE_API_KEY` nötig) | Niedrig, aber lizenzpflichtig | ⚠️ bereits als Workaround markiert, laut Memory *"custom Jarvis-Modell noch nicht trainiert, Porcupine nur Übergangslösung"* — genau das Problem, das hier gelöst werden soll |
| **Eigenes NN von Grund auf** | ✅ | ✅ | **Hoch** — Datensammlung, Architektur, Training, Evaluierung von Null | Kein Mehrwert ggü. openWakeWord, das dasselbe bereits liefert |

**Klare Empfehlung: openWakeWord-Custom-Training.** Es ist bereits im Repo
vorhanden, CPU-only, deckt exakt die im Auftrag genannten Anforderungen ab
(Datenschutz, keine Cloud, geringe Ressourcen) und löst nebenbei das seit
Längerem zurückgestellte Ziel eines eigenen Wake-Word-Modells ohne
Porpoicine-Abhängigkeit.

### Generalisierung vs. Personalisierung

Das README bestätigt: die mitgelieferten Modelle sind zu **100 % aus
synthetischer Sprache** trainiert und trotzdem robust gegenüber
verschiedenen echten Stimmen/Akzenten — das deckt die Anforderung
"allgemeines Modell, nicht nur meine Stimme" ohne zusätzlichen Aufwand ab.
Für Personalisierung (optionale zweite Stufe) beschreibt
`docs/custom_verifier_models.md` einen **Custom-Verifier** — ein zweites,
kleines Modell, das nur auf eine bestimmte Stimme reagiert und als
Nachfilter auf die allgemeine Erkennung läuft. Das lässt sich später
optional ergänzen, ohne das Basis-Modell neu zu trainieren.

## 5. Integration in die bestehende Architektur

Minimal-invasiv, da `wakeword.py` bereits für beliebige openWakeWord-Modelle
gebaut ist:

1. Trainiertes `kev_v0.1.onnx` nach
   `openWakeWord-0.6.0/openwakeword/resources/models/` legen.
2. `_OWW_MODEL_MAP` in `jarvis/voice/wakeword.py:24-32` um
   `"kev": "kev_v0.1.onnx"` ergänzen.
3. `config/default.yaml` → `wakeword.model_name: "kev"`,
   `wakeword.backend: "openwakeword"` setzen (weg von `porcupine`).
4. Bestehende Sonderregel `model == "jarvis"` → `patience = 1`
   (CLAUDE.md, `pvporcupine`-Pfad) entfällt für "kev", da openWakeWord einen
   eigenen, konfigurierbaren `patience`/`threshold`-Mechanismus nutzt
   (bereits vorhanden in `_process_openwakeword`).
5. Keine Proto-/gRPC-/WinUI-Änderung nötig — die Erkennung ist reine
   Backend-Logik, das Frontend sieht nur den Wake-Event.

**Das ist ausdrücklich getrennt von einer vollständigen Umbenennung**
(UI-Strings, Log-Präfixe, Installer-Name, Repo-Name — siehe ADR-003). Ein
neues Wake-Word kann unabhängig von der Namensentscheidung entwickelt und
getestet werden, während "JARVIS" als Produktname vorerst bestehen bleibt.

## 6. Aufwandsschätzung

| Schritt | Aufwand | Bemerkung |
|---|---|---|
| Marken-/Domain-Klärung für finalen Namen | 0,5–1 Tag (extern/Nutzer) | Kein Code, aber Voraussetzung für Phase 8 (Rebranding) |
| Synthetische Trainingsdaten generieren | Wenige Stunden CPU-Zeit, unbeaufsichtigt | Notebook-gesteuert, kein manuelles Sammeln |
| Modell-Training + Threshold-Tuning | Wenige Stunden, iterativ | Inkl. Test gegen reale Alltagssprache (False-Accept-Rate) |
| Integration in `wakeword.py` + Config | **< 1 Stunde Code** | Minimal-invasiv, siehe Abschnitt 5 |
| End-to-End-Test (Live-Mikrofon, 30+ Min.) | 0,5 Tag | Wie in `jarvis-engineering`-Skill gefordert |
| **Gesamt (nur Wake-Word, ohne Rebranding)** | **~1–2 Arbeitstage** | Kann parallel zur Namensklärung laufen |
| Vollständiges Rebranding (UI, Logs, Installer, Repo) | Separates, größeres Vorhaben | Sollte eigenes ADR + Phase erhalten, siehe ADR-003 |

## 6b. Vertiefte Prüfung: 3-Buchstaben-Namen (Nachtrag 2026-07-13)

Auf Wunsch des Nutzers wurde die Recherche auf weitere kurze, aussprechbare
3-Buchstaben-Namen im Stil von "Kev" ausgeweitet (Web-Recherche, jeweils
gezielt nach "\<Name\> AI assistant / existing product" gesucht). Ergebnis:
**alle acht geprüften Kandidaten sind bereits belegt.** Der Namensraum für
kurze, personennamen-artige KI-Assistenten-Namen ist im Jahr 2026 praktisch
gesättigt.

| Name | Gefundene Kollisionen | Schweregrad | Anmerkung |
|---|---|---|---|
| **Kev** | Kev.AI (personalisierter KI-Chatbot, Otter Property Management), Domain `kev.ai` belegt | **Niedrig-mittel** | Kleines/Nischen-Produkt, keine große Marke dahinter |
| **Ivo** | Ivo.ai — KI-Vertragsanalyse für Legal-Teams (IBM, Uber, Shopify als Kunden genannt), $4,8 Mio. Funding | **Niedrig-mittel** | Anderes Marktsegment (B2B-Legal-Tech, nicht Consumer-Assistent), aber real finanziertes Unternehmen |
| **Jax** | JaxAI (On-Device-KI-Begleiter-App), "Jax: Artificial Intelligence" (**explizit "inspired by Jarvis"** beworben), Jaxo.ai, Jaxon.ai, JAX (Xero-Buchhaltungstool), Google JAX (ML-Framework) | **Mittel** | Sehr viele Treffer, aber meist kleinere Apps |
| **Nox** | NOX (macOS Messaging-KI), "NOX — AI Operating System / Total Device Intelligence" (**konzeptionell fast identisch zu JARVIS/Kev**), Nox AI Coach, NoxAI (Agentur) | **Mittel-hoch** | Eines der Produkte beschreibt sich fast wortgleich zum eigenen Vorhaben |
| **Rex** | Mind. 8 unterschiedliche aktive "Rex"-KI-Produkte (Compliance, Order-to-Cash/YC-finanziert, Real-Estate-CRM, AWS-Copilot, Incident-Response) | **Hoch** | Extrem gesättigt über viele Branchen |
| **Kai** | Mind. 5 unterschiedliche aktive "Kai"-Produkte, u. a. **Kasisto KAI** — etabliertes B2B-Conversational-AI-Produkt für Banken (seit ~2014) | **Hoch** | Kasisto KAI ist eine seit Jahren am Markt etablierte, wahrscheinlich markenrechtlich abgesicherte Plattform |
| **Zed** | **Zed Industries** — gut finanzierter, bekannter KI-Code-Editor (zed.dev), starke Marke im Dev-Tools/AI-Raum | **Hoch** | Prominente, gut finanzierte Marke mit direktem KI-Bezug |
| **Eno** | **Eno von Capital One** — Flaggschiff-KI-Assistent einer großen Bank, seit 2017, massiv beworben | **Sehr hoch** | Große, gut geschützte Marke eines Fortune-500-Unternehmens |

**Muster:** Praktisch jeder kurze, sprechbare, personennamen-artige Name ist
2026 bereits von mindestens einem KI-Produkt belegt — der "Gold Rush" der
letzten Jahre hat den Namensraum weitgehend aufgebraucht. Das ist kein
Kev-spezifisches Problem, sondern eine generelle Marktbeobachtung.

**Wichtige Einordnung — reale vs. theoretische Rechtsgefahr:** Diese
Recherche zeigt *Namenskollisionen*, keine bestätigten eingetragenen Marken.
Markenrecht greift primär bei **kommerzieller Nutzung im geschäftlichen
Verkehr, die Verwechslungsgefahr erzeugt**. JARVIS/Kev ist aktuell ein
privates, nicht-kommerzielles Assistenzsystem für den Eigengebrauch — das
rechtliche Risiko ist dadurch deutlich geringer als bei einem
Markt-Launch. Falls perspektivisch eine Veröffentlichung (auch kostenlos,
z. B. GitHub-Release mit Nutzerbasis) geplant ist, ändert sich diese
Einschätzung — dann wäre eine formale Markenrecherche (DPMA/EUIPO, nicht nur
Web-Suche) vor der finalen Festlegung sinnvoll.

**Rangfolge nach geprüftem Kollisionsrisiko (niedrig → hoch):**
1. **Kev** (Nischenprodukt, geringste Sichtbarkeit)
2. Ivo (anderes Marktsegment, aber real finanziert)
3. Jax (viele, aber überwiegend kleine Treffer)
4. Nox (ein Treffer konzeptionell sehr nah)
5. Rex (breite Sättigung)
6. Kai (etablierte Enterprise-Plattform dabei)
7. Zed (prominente, gut finanzierte Marke)
8. Eno (Fortune-500-Flaggschiffprodukt — klar meiden)

## 7. Empfehlung (aktualisiert nach 3-Buchstaben-Check)

1. **Kein geprüfter Kandidat ist kollisionsfrei** — auch nach Ausweitung auf
   sieben Alternativen bleibt "Kev" der am wenigsten belastete Name (Rang 1
   von 8, siehe 6b). Eine perfekte, unbelastete Kurzform existiert im
   aktuellen KI-Namensmarkt praktisch nicht.
2. **Für ein privates, nicht-kommerzielles Projekt ist das reale Risiko bei
   "Kev" gering** (siehe Einordnung in 6b) — kein Grund, die Umsetzung
   deswegen zu blockieren. Falls jemals eine öffentliche Veröffentlichung
   ansteht, dann vorher eine formale Markenrecherche (DPMA/EUIPO) nachholen.
3. **Empfehlung: "Kev" beibehalten und mit der Umbenennung fortfahren**,
   mit dem Wissen, dass Kev.AI als einziges reales Kollisionsprodukt existiert
   (kleines Nischenprodukt, keine große Marke).
4. **Wake-Word-Training bleibt namensunabhängig planbar** und sollte parallel
   zur Umbenennung angestoßen werden (siehe Abschnitt 4/5) — das Wake-Word
   selbst heißt technisch weiterhin `hey_jarvis`, bis ein `kev`-Modell
   trainiert und validiert ist.

**Status dieses Dokuments:** Analyse/Vorschlag, Namensrecherche abgeschlossen.
Umsetzungsumfang der Umbenennung (nur sichtbare Ebene vs. vollständig inkl.
Code-Identifier) wird als nächster Schritt mit dem Nutzer abgestimmt, bevor
Dateien geändert werden.

## 8. Erweiterte Suche (Nachtrag 2026-07-13): 24 Kandidaten geprüft, "frei" gefordert

Der Nutzer hat präzisiert: die Marke muss frei sein, nicht nur "am wenigsten
belastet". Da "Kev" und alle sieben ursprünglichen Alternativen belegt waren
(Abschnitt 6b), wurde die Suche auf zwei- bis dreisilbige, DE/EN-aussprechbare
Kunstnamen jenseits typischer Startup-Muster ausgeweitet — 24 Kandidaten
insgesamt gegen "\<Name\> AI assistant app" plus Domain-/Marken-Nachsuche
geprüft.

### Belegte Kandidaten (dieser Runde)
Zorik, Vellan, Milek(✓ frei, s.u.), Orvin, Kesto (Kyocera-Produkt),
Ryven, Corvis, Falken/Falkor, Perlo, Wenlo(✓ frei), Renvo, Torven, Alvek
(Näheumfeld zu Alva/Alvin belegt).

### Ohne Produkt-Treffer geblieben (10 von 24)

| Kandidat | Web-Befund | Aussprache DE/EN | Einschätzung |
|---|---|---|---|
| **Tarno** | Keine Produkt-Treffer, auch nicht bei Domain-/Markensuche | Sehr gut | **Top-Empfehlung** |
| **Doven** | Keine Produkt-Treffer (nur ähnliche: Dove, Dover, Doubai) | Gut | Starker Zweitkandidat |
| **Darvyn** | Keine Produkt-Treffer (nur ähnlich: Darwin AI, andere Schreibweise) | Gut | Starker Kandidat |
| **Sorvin** | Keine exakten Treffer, aber phonetisch nah an "Soverin" (E-Mail-Hoster) | Gut | Leichter Restzweifel |
| **Milek** | Nur Personennachname-Treffer (kein Produkt) | Gut | Solide |
| **Miklo** | Nur ähnliche Namen (Miko, Milo, Mico) — kein exaktes "Miklo" | Gut | Solide |
| **Onvar** | Keine Treffer | Mittel (etwas ungewöhnlich) | Solide |
| **Sevlo** | Keine Treffer (nur ähnliche: Sevva, Sevalla) | Gut | Solide |
| **Brenlo** | Keine Treffer (nur ähnliche: Brello, Bren) | Gut | Solide |
| **Wenlo** | Keine Treffer (nur ähnliche: Wenxin) | Gut | Solide |

### Wichtige Einschränkung dieser Methode

Ich habe **kein Werkzeug für eine echte WHOIS-/Domain-Verfügbarkeitsabfrage
oder eine formale Markenregister-Abfrage** (DPMA/EUIPO/USPTO-Datenbank direkt).
"Keine Web-Treffer" ist ein starkes Indiz für Nicht-Existenz als aktives
Produkt, aber **kein Beweis für freie Eintragung im Markenregister oder freie
Domain**. Vor einer finalen Festlegung: die Top-Kandidaten (v. a. `tarno.de`/
`tarno.com`) einmal manuell bei einem Registrar (Namecheap, IONOS, Cloudflare)
auf Domain-Verfügbarkeit prüfen — das dauert 30 Sekunden und ist etwas, das
ich technisch nicht selbst ausführen kann.

### Empfehlung (aktualisiert)

**"Tarno"** ist nach 24 geprüften Kandidaten der sauberste Treffer — keine
einzige Kollision, auch nicht bei vertiefter Nachsuche (im Gegensatz zu z. B.
"Vynn" oder "Sorvin", wo eine zweite Suchrunde doch noch Treffer brachte).
Zweit- und Drittwahl: **"Doven"** und **"Darvyn"**, ebenfalls ohne
Produkt-Kollision gefunden.
