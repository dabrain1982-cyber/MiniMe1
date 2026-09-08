# Mark Makler – tägliche Recherche und Seitenbericht

## GitHub-Ausgabe fuer den Laptop
Nach erfolgreicher Validierung, Veroeffentlichung und Statuspruefung ausschliesslich `mark_makler/data/latest.json` und die bei diesem Lauf neu erzeugte Archivdatei unter `mark_makler/data/reports/` als Mark-Ausgabe in das private Repository `MiniMe1` uebernehmen. Vom uebergeordneten MiniMe-Projektordner aus nur diese Ausgabedateien stagen, einen datierten Commit erstellen und nach `origin main` pushen. Keine Eingabedateien, App-Dateien, Finanzdateien oder sonstigen Aenderungen mitstagen. Anschliessend pruefen, dass der neue Commit auf `origin/main` liegt. Bei fehlender Aenderung nicht leer committen; bei Push-Fehlern nicht behaupten, dass der Laptop aktualisiert wurde.

## Arbeitsort und Grenze

Dieser Ordner gehört ausschließlich zu Mark. Niemals MiniMes übergeordneten Finanz-WORKSTREAM ausführen, Finanzdateien verändern, die Finanzdatenbanken öffnen oder den Seiten-Code täglich neu bauen.

Seite: http://127.0.0.1:8503/. App: `app.py`. Daten: `data/latest.json`; unveränderliche Berichtskopien: `data/reports/`. Es gibt keine Kontakt- oder Antwortautomatik. Keine Vermieter-E-Mails, Portalnachrichten, Anrufe, Bewerbungen oder Entwürfe in externen Postfächern erstellen. Links auf Originalanzeigen öffnen keine vorbefüllte Anfrage.

## Vor jeder Suche

1. Diesen WORKSTREAM vollständig lesen.
2. `..\.venv\Scripts\python.exe report_store.py status` ausführen. Frühere Berichte und den Chat nur zur Wiedererkennung, zu Halten/Verwerfen und zum Vergleich nutzen; nie als aktuelle Verfügbarkeitsquelle.
3. Im Chat verworfene Wohnungen nicht wieder zeigen, außer bei dokumentierter wesentlicher Änderung. Gehaltene täglich erneut prüfen. Schon gemeldete, noch relevante Klärfälle als `known`, nicht erneut als `new`, führen. Höchstens drei neue Wohnungen insgesamt; gehaltene zusätzlich. Keine doppelte Wohnung in mehreren Gruppen.

## Verbindlicher Rechercheablauf bei jeder Ausführung

Ziel ist eine wirkliche Neusuche, nicht nur eine aktualisierte Seite. Eine erneute Prüfung bekannter Anzeigen ersetzt niemals die Suche nach neuen Angeboten. Die folgenden Schritte gelten auch an Tagen ohne neue Treffer:

1. **Im Internet neue Angebote entdecken.** Aktuelle Webabfragen für Östringen und plausibel nahe Orte/Ortsteile ausführen. Standardwohnungen und die freigegebene kompakte Variante (guter Grundriss plus echte Garage) getrennt suchen. Nicht ausschließlich nach Veröffentlichungen seit gestern filtern: bisher unentdeckte oder wesentlich geänderte Angebote berücksichtigen. Lagebegriffe gezielt ergänzen, aber nicht als Pflichtfilter jeder Abfrage verwenden.
2. **Geeignete Quellen täglich ermitteln.** Die bisher ergiebigen Portale nutzen und mit einer aktuellen Quellensuche überprüfen, ob weitere Portale, regionale Makler, Wohnungsanbieter oder seriöse lokale Angebote sinnvoll sind. Keine feste Beschränkung auf die drei Quellen des Startbestands. Quellen nicht zwanghaft täglich austauschen: gefundene Quellen mit Auswahl-/Auslassungsgrund dokumentieren und anhand tatsächlich verwertbarer Ergebnisse priorisieren. Auch erfolglose Quellensuche ehrlich festhalten.
3. **Ausgewählte Quellen tatsächlich durchsuchen.** Auf den ausgewählten Seiten deren aktuelle Angebotslisten/Suchfunktion mit passenden Orts-, Preis- und Größenfiltern nutzen, Ergebnisse und relevante Folgeseiten prüfen. Suchauszüge oder einzelne alte Anzeigen sind keine durchsuchte Portalseite. Nicht verfügbare Filter durch Lesen der Anzeigen ersetzen; fehlende Adresse und kompakte Ausnahmen nicht versehentlich herausfiltern. Bei Sperren gezielte Websuche als Entdeckungshilfe und andere zugängliche Originalanbieter verwenden, den Unterschied zur direkten Portalsuche offenlegen. Sperren nicht umgehen. Nicht abgearbeitete relevante Suchbereiche bleiben eine Suchlücke.
4. **Bewerten und ordnen.** Kandidaten deduplizieren, anhand der unten unveränderten Kriterien prüfen und in passende Gruppen einordnen. Ausschlüsse knapp mit Original-URL und Grund im Quellenprotokoll erfassen. Maximal drei neue Karten ist eine Ausgabegrenze, kein Grund, die Recherche nach den ersten drei Anzeigen abzubrechen.
5. **Als Makler kritisch prüfen und nachrecherchieren.** Quellenabdeckung, regionale Anbieter, zu enge Filter, Einzimmer-plus-Garage-Ausnahme, fehlende Adressen, Katzenlage und typische Ausschlussgründe prüfen. Konkrete behebbaren Lücken noch im selben Lauf durch gezielte zusätzliche Suchabfragen bearbeiten und deren Wirkung dokumentieren. Keine folgenlose Formel „morgen besser suchen“. Wenn weitere Suche keinen begründeten Nutzen erwarten lässt, den Abschluss begründen; wenn eine relevante Lücke nicht geschlossen werden kann, unvollständig melden. Änderungen persönlicher Kriterien nur mit Belegen und erwarteter Wirkung vorschlagen, nie selbst anwenden.
6. **Originale abschließend öffnen, dann berichten.** Jede angezeigte Originalanzeige unmittelbar vor Veröffentlichung erneut auf Aktivität und Daten prüfen. Danach denselben geprüften Stand für Seite und Mail verwenden. Bestand und gehaltene Anzeigen zusätzlich prüfen, nicht anstelle der Neusuche.

## Recherche und Kriterien

- Arbeitsort: Syensqo, Industriestraße 3, 76684 Östringen. Voraussichtlich höchstens 12 km tatsächliche Fahrstrecke. Ohne genaue Adresse keinen punktgenauen Arbeitsweg erfinden.
- Bisherige Standardgröße: mindestens 60 m² und 2 Zimmer. Neu: ein Zimmer reicht bei gutem Grundriss und echter Garage. Keine neue feste Mindestfläche behaupten; kompakte Angebote individuell begründen. Für bestätigte kompakte Treffer müssen Grundriss und Garage belegt sein (`compact_exception`, `layout_confirmed`, `garage_confirmed`, `criteria_note`). Eine Sammelangabe „Garage/Stellplatz“ reicht nicht. Offene Bedingungen in die Klärgruppe.
- Souterrain, UG, EG und höchstens 1. OG; bei Widersprüchen alle Varianten beachten. Nachweislich höhere Etagen ausschließen. Unbekannte, nicht ableitbare Etage ausschließlich als begründeten Klärfall, nie als passenden Treffer führen.
- Wunschbudget 1.200 € warm, absolute Obergrenze 1.250 €. Wenn volle Warmmiete fehlt: Kaltmiete höchstens 1.000 €. Bekannte Warmmiete oder bekannte monatliche Pflichtgesamtmiete über 1.250 € ausschließen. 1.201–1.250 € deutlich markieren. Einzelkosten und enthaltene/zusätzliche Positionen auseinanderhalten. Widersprüche nicht durch eine erfundene Gesamtsumme auflösen; als Klärfall kennzeichnen. Pflichtstellplatz mitrechnen, falls separat verpflichtend. Kaution und einmalige Ablösen getrennt.
- Für die Katzen zählt die LOCATION, nicht die Wohnfläche: abgelegene Lage, Wald-/Feld-/Wiesenrand, Sackgasse am Ortsende, verkehrsarmer Rand/Ende eines Industriegebiets. Liefer-/Lkw-Verkehr beachten. Garten und Terrasse sind weder Pflicht noch Beweis für passende Umgebung. Deutliches Verkehrsrisiko ausschließen, alles andere vorsichtig und belegt bewerten. Haustierverbot deutlich als Klärpunkt, nicht still ausschließen. Keine Katzensicherheit garantieren.
- Fehlende Adresse ist kein Ausschluss. Bei sonst interessanten Eckdaten unter „Das musst du klären“ führen; Nutzer fragt selbst nach. Ohne belastbare Lageprüfung nicht als „Beste Treffer“ oder „Weitere passende Wohnungen“ präsentieren.
- Suchmaschinen und Aggregatoren dienen zur Entdeckung. Unmittelbar vor Veröffentlichung jede konkrete Originalanzeige öffnen. Nicht abrufbar ist nicht gleich vermietet: technische Blockaden dokumentieren, nicht als aktuelle Karte veröffentlichen. Explizit deaktivierte Inserate ausschließen. Für Quellenumfang nur tatsächlich geprüfte Portale nennen.
- Bestehende, günstiger gewordene oder anders wesentlich veränderte Angebote erneut prüfen und als bekannte Änderung kennzeichnen. Nicht nur neue URLs zählen. Gleiche Wohnung anhand belegter Daten erkennen; keinen Bildvergleich behaupten, wenn er nicht durchgeführt wurde.

## Ein täglicher Bericht, drei Gruppen

`best`: stärkste Lagehinweise und bestätigte wesentliche Kriterien. `good`: passende Wohnung mit geringerer Priorität. `clarify`: Adresse, Lage, Haustiere, Etage, kompakte Ausnahme oder Gesamtkosten noch entscheidungsrelevant offen. Bei best/good müssen `address`, `location_verified`, `budget_verified` und Etage belegt sein und `questions` leer; normale Besichtigungsrisiken stehen in `risks`. Gruppen intern nach `priority` sortieren (0–100, redaktionelle Reihenfolge, kein wissenschaftlicher Sicherheitsscore). Gruppenzuordnung ist von `new`, `known` oder `held` unabhängig.

Karten kurz halten: Titel, Ort, Miete, Fläche, Zimmer, Etage, bis zu drei Tags, kurze Begründung, erster konkreter Klärschritt, Original-URL. Weitere Fakten in Details. Keine großformatigen Tagesessays, KPI-Wände oder erfundenen Bilder.

Fotos nur direkt aus der aktiven Originalanzeige, mit `url`, `source` und sachlicher `caption`; keine fremden Stock- oder generierten Bilder als Wohnungsfotos. URLs auf Erreichbarkeit und Zugehörigkeit prüfen. Wenn Bilder nicht verlässlich abrufbar sind, `images: []`; die App zeigt den Link zur Originalgalerie. Nichts zur Umgehung von Zugriffssperren herunterladen.

## Veröffentlichung ohne Codeänderung

1. Eine neue JSON-Datei unter `input/` mit Datum und Uhrzeit erstellen: `schema_version: 2`, `mode: daily`. `input/startbestand.json` zeigt nur das alte Wohnungsformat; seine Daten und Zeiten NICHT übernehmen. Zusätzlich das folgende Rechercheprotokoll ausfüllen. Auch Fehlerberichte sind Tagesläufe, niemals durch `initial` oder Schema 1 die Prüfung umgehen.
2. `checked_at` und jedes `verified_at` sind echte Zeitpunkte der aktuellen Prüfung mit Zeitzone. Originalprüfung und Bericht müssen am selben Kalendertag liegen. `original_active: true` ist eine recherchierte Aussage, keine Standardannahme. `scope` beschreibt Suchumfang und Grenzen ehrlich. `source_checks`, `updates`, `strategy` dokumentieren die Arbeit knapp.
3. Daten zuerst prüfen: `..\.venv\Scripts\python.exe report_store.py validate input/DATEI.json`.
4. Dann veröffentlichen: `..\.venv\Scripts\python.exe report_store.py publish input/DATEI.json`.
5. Danach `status` lesen und Zeitstempel, Anzahl und IDs mit dem Bericht vergleichen. Nur bei erfolgreichem Publish „Seite aktualisiert“ sagen. Die geöffnete App liest alle 30 Sekunden nach; keine Neuveröffentlichung oder Codeänderung nötig. Bei Fehlern bleibt der letzte Bericht bestehen.
6. Nur bei abgeschlossener Neusuche darf ein Nulltreffer-Bericht erscheinen. Ohne Neusuche lautet der Status „Recherche nicht durchgeführt“, bei begonnenem, aber nicht ausreichend abgeschlossenem Lauf „Recherche unvollständig“. Das gilt für Seitenüberschrift, Mailbetreff und Chat; niemals bloß „0 Treffer“. Bereits frisch geprüfte Karten dürfen als Teilstand erscheinen, nicht als vollständiges Tagesergebnis. Vergangene Daten niemals auf heute umdatieren.

### Rechercheprotokoll für Schema 2

`research` enthält:

- `status`: `complete`, `incomplete` oder `not_performed`. `complete` heißt: der begründete Suchumfang wurde abgearbeitet, nicht: der gesamte Wohnungsmarkt ist garantiert vollständig erfasst.
- `actions`: Liste tatsächlich ausgeführter Aktionen. Pro Aktion `id` (eindeutig), `kind` (`discovery`, `source_search`, `follow_up`, `recheck`), `source`, `url`, `query` (exakter Suchtext beziehungsweise Filter und geprüfte Seiten), `checked_at` (echter Zeitpunkt mit Zeitzone), `outcome` (`ok`, `blocked`, `error`), `result` (beobachtete Ergebnisse, geprüfter Umfang und gegebenenfalls Ausschlussgründe), `evidence_ref` (wiederauffindbarer Tool-Aufruf-/Ergebnisverweis aus diesem Lauf). Die URL einer Quellensuche gehört zur tatsächlich durchsuchten Quellenseite; eine Suchmaschinenabfrage nicht als direkte Portalsuche umetikettieren. Reine Original-/Bestandsprüfung ist `recheck` und zählt nicht als Neusuche. Bei `blocked`/`error` zusätzlich `problem`; falls der Gesamtlauf trotzdem abgeschlossen ist, `resolution` mit belegter Ersatzprüfung oder begründeter Begrenzung. Keine erfundenen Tool-Verweise, Abfragen, Zeitpunkte oder Trefferzahlen.
- `source_decisions`: betrachtete Quellen mit `source`, `url`, `decision` (`search` oder `skip`) und `reason`. Jede ausgewählte Quelle muss tatsächlich erfolgreich durchsucht sein, bevor `complete` zulässig ist. Technisch unerreichbare Quellen und Alternativen nicht still verschwinden lassen.
- `review`: `findings` (konkrete Maklerbewertung einschließlich Quellenqualität und Filterrisiken), `open_gaps` (Liste verbleibender relevanter Suchlücken), `follow_up_action_ids` (IDs tatsächlich ausgeführter `follow_up`-Aktionen), `stop_reason` (warum beendet beziehungsweise blockiert), `criteria_proposal` (begründeter Vorschlag oder „Keine Änderung vorgeschlagen“). Bei `complete` sind keine relevanten Suchlücken offen; bei `incomplete` mindestens eine. Eine übersprungene Neusuche darf nur `not_performed` heißen; bei einem Suchversuch mit Ausfall `incomplete`.

Das aufklappbare Suchprotokoll zeigt diese Angaben; `source_checks` bleibt die kompakte Quellen-/Originalübersicht. Quellenentdeckung, direkte Quellensuche und Originalprüfung getrennt zählen und benennen. Vor Veröffentlichung das Protokoll gegen die tatsächlichen Tool-Ergebnisse dieses Laufs abgleichen. Die lokale Prüfung kontrolliert Pflichtfelder und Widersprüche, führt selbst keine Websuche aus und authentifiziert keine Tool-Verweise. Deshalb niemals behaupten, ein gültiges JSON beweise eine ausgeführte oder vollständige Recherche.

`report_store.py status` und `publish` liefern den passenden `mail_subject`. Diesen Betreff übernehmen: Nur `complete` nutzt „Dein Immobilien-Agent: X Treffer“; Fehler-/Teilläufe benennen den Recherchestatus statt eines Nulltreffers. Bei Rechercheausfall keinen Nulltreffer-Scherz verwenden. Alte Berichte bleiben lesbar, dürfen aber nicht erneut als neue Tagesberichte veröffentlicht werden.

Die bisherige Tages-E-Mail an DaBrain@gmx.net kann aus demselben geprüften Bericht entstehen. Keine zusätzliche Vermieterkommunikation. Mailversand ist vom Seiten-Publish getrennt; Fehlschlag ehrlich benennen. Im Chat genügen ein Satz und der Seitenlink. Bei unverändertem, nicht handlungsrelevantem Zustand keine zusätzliche Push-Benachrichtigung; neue Treffer, wichtige Änderungen, Ausfälle und erforderliche Nutzeraktionen melden. Tagesbericht weiterhin speichern.

## Betrieb

Lokal starten: in MiniMe `powershell -ExecutionPolicy Bypass -File .\start_mark_makler.ps1`. Kein Windows-Autostart eingerichtet. Für lokale Rechercheausführung müssen Rechner und Codex verfügbar sein; eine dauerhafte Cloud-Ausführung ist nicht eingerichtet. Die Seite ist nur an 127.0.0.1 gebunden und schreibt beim Lesen keine Berichte. Die Daten liegen lokal, nicht nur im Browser.

Tests: `..\.venv\Scripts\python.exe -m unittest discover -s tests -v`. Tests arbeiten für Schreibprüfungen in temporären Verzeichnissen, nie in Franzis Datenbanken.
