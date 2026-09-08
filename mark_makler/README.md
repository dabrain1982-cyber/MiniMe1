# Mark Makler

Separate lokale Wohnungsübersicht in MiniMe. Franzis App und Finanzdaten bleiben unverändert.

## Freigegebener Umfang

- Kurzer Tagesstand, danach sortierte Wohnungskarten.
- Beste Treffer zuerst, weitere passende Wohnungen danach, Klärfälle gesammelt darunter.
- Echte Originalanzeigen und nachweisbare Angaben; keine fiktiven Angebote im laufenden Bericht.
- Für die Katzen zählt die abgelegene, verkehrsarme Lage, nicht die Wohnungsgröße.
- Ein Zimmer ist bei gutem Grundriss und Garage grundsätzlich möglich. Eine neue feste Mindestfläche ist noch nicht vereinbart.
- Keine Kontaktaufnahme mit Vermietern und keine automatische Antwortverarbeitung.
- Keine öffentliche Veröffentlichung; zunächst eine lokale Seite wie bei Franzi.

## Start

In MiniMe `start_mark_makler.ps1` ausführen und http://127.0.0.1:8503/ öffnen.
Die bestehende `.venv` wird nur als Laufzeit benutzt. Keine Änderungen an Franzis App oder Abhängigkeiten.

Die App zeigt `data/latest.json`, gruppiert und priorisiert die Wohnungskarten und liest neue Berichte alle 30 Sekunden. Der Startbestand enthält reale, am 07.09.2026 erneut geprüfte bekannte Anzeigen; keine fiktiven Mockup-Inhalte.

## Berichte und Qualität

Der vollständige Ablauf steht in `WORKSTREAM.md`. Neue Berichte mit `report_store.py validate` prüfen und mit `report_store.py publish` atomar speichern. Der Publisher archiviert jeden unterschiedlichen Bericht; bekannte, neue und gehaltene Wohnungen bleiben unterscheidbar. Er führt selbst keine Webrecherche aus und kann Anbieterangaben nicht eigenständig bestätigen.

Seit 08.09.2026 benötigen neue Veröffentlichungen Schema 2 mit Suchaktionen, Quellenwahl und abschließender Maklerprüfung. Web-/Quellenentdeckung und die Suche in ausgewählten Quellen sind getrennt von der Bestandsprüfung. „Recherche nicht durchgeführt“ und „Recherche unvollständig“ erscheinen als eigene Zustände, nicht als Nulltreffer. Der passende Mailbetreff wird von `status`/`publish` ausgegeben. Die Prüfung kontrolliert deklarierte Belege und Konsistenz; sie authentifiziert keine Tool-Aufrufe und garantiert keine vollständige Marktabdeckung. Alte Berichte bleiben unverändert lesbar, können aber nicht erneut veröffentlicht werden.

Tests: aus diesem Ordner `..\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

Keine öffentliche Website, kein Windows-Autostart und kein eigenständiger Cloud-Agent. Bilder werden mit Quellenhinweis vom jeweiligen Anbieter geladen; die Anbieter erhalten dabei technisch bedingt Bildabrufe vom Browser.
