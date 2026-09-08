# ING-Import und Finanzbilanz

Aktualisierung nach gemeinsamer Klärung: Alle 48 offenen Zuordnungen wurden bestätigt
und übernommen. Amazon-Einkäufe bleiben bewusst ohne Warenkategorie, Prime separat.
Die 2.883,12 € Gutschriften sind als Erstattungen/Kautionsrückzahlung eingeordnet;
die Mietkaution von 1.370,00 € ist Teil 1 von 2, Teil 2 steht noch aus.
Die Übersicht stellt jetzt den monatlichen Kontozuwachs dar. Amazon hat eine eigene
Monatsanzeige in beiden Ansichten. Die folgenden Importzahlen und der damalige
Prüfstatus dokumentieren den ursprünglichen Import; Beträge und Salden sind unverändert.

Stand: 06.09.2026. Fünf echte Auszüge April bis August 2026 wurden lokal importiert.

| Monat | Buchungen | Kontozuwachs | Endstand | Abstimmungsdifferenz |
| --- | ---: | ---: | ---: | ---: |
| April | 43 | +1.247,27 € | 4.304,33 € | 0,00 € |
| Mai | 41 | +3.181,03 € | 7.485,36 € | 0,00 € |
| Juni | 45 | +730,04 € | 8.215,40 € | 0,00 € |
| Juli | 41 | +447,22 € | 8.662,62 € | 0,00 € |
| August | 35 | +741,87 € | 9.404,49 € | 0,00 € |

205 Buchungen, 6.347,43 € Kontozuwachs. Anfangsstand April: 3.057,06 €.
48 Kategorien bleiben zu prüfen. Drei ungeklärte Gutschriften von zusammen
2.883,12 € sind im Kontostand enthalten, jedoch noch nicht unter Einnahmen eingeordnet.
Als Einnahmen eingeordnet: 14.162,19 €. Ausgaben: 10.697,88 €.

## Nachweise

- Eigenes ING-Profil für Buchungsdatum, darunterliegende Wertstellung, mehrzeilige Texte,
  rechtsstehende Beträge, Monatsüberschrift und alte/neue Salden.
- Alle Buchungsdaten und Beträge mit einer unabhängigen PDF-Bibliothek und
  geometrischer Spaltenauswertung verglichen: vollständige Übereinstimmung.
- Salden aller Monate cent-genau; Monatsübergänge lückenlos.
- Testdatenbank: jeder Auszug zweimal angeboten, keine Doppelimporte.
- Zwölf automatisierte Tests erfolgreich; zusätzlich alle fünf befüllten Monatsansichten
  ohne Streamlit-Ausnahmen geprüft.
- Drei Reiter am Desktop visuell geprüft; schmale Ansicht zusätzlich kontrolliert.
- Prüfsummen und maskierte Kontoidentifikation; Original-PDFs unverändert.

## Nutzung und Grenzen

Start: start_finanzbilanz.ps1. Ansicht: http://localhost:8501/.
Neue ING-PDFs dieses Formats direkt in der App hochladen und nach der Vorschau importieren.
Die App benötigt dafür keinen KI-Dienst. Abweichende Salden sperren den Import.
Änderungen des Banklayouts und nicht textbasierte Scans können eine Anpassung erfordern.
Kategorien sind nicht gleichbedeutend mit rechnerischer Bestätigung. Gemischte Händler
und unklare Gutschriften benötigen weiterhin eine inhaltliche Klärung.

Datenbank: data/finanzbilanz.sqlite3. Maschineller Prüfbericht: data/importpruefung.json.
Entwicklerprüfung: verify_ing_import.py mit den PDF-Pfaden als Argumenten;
benötigt zusätzlich pdfplumber (im gebündelten Prüf-Python verfügbar).
Ohne --import schreibt die Prüfung keine Buchungen in die produktive Datenbank.

Aktueller Verbesserungsvorschlag: ungeklärte Gutschriften und wiederkehrende Händler
gemeinsam klären. Eine Umsetzung persönlicher Zuordnungsentscheidungen erfolgt erst
nach Bestätigung.
