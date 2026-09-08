"""Apply the user's reviewed April-August decisions, with a local backup."""
from pathlib import Path
import sqlite3
from datetime import datetime
from finance_core import normalize_key, _merchant_and_category


def main():
    root = Path(__file__).parent
    db = root / 'data/finanzbilanz.sqlite3'
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    backup = db.with_name('vor-zuordnungen-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
    with sqlite3.connect(backup) as dest:
        conn.backup(dest)
    decisions = [
        ('csc gruene liebe', 'CSC Grüne Liebe', 'Freizeit, Sport und Kultur', 'Cannabisclub-Mitgliedsbeitrag'),
        ('hgv kraeutergarten', 'HGV Kräutergarten', 'Freizeit, Sport und Kultur', 'Pflanzenanbau: Cannabispflanzen'),
        ('sinowell', 'Vivosun', 'Freizeit, Sport und Kultur', 'Pflanzenanbau: Vernebler'),
        ('vapore', 'Vapore', 'Tabak und E-Zigaretten', 'E-Zigaretten-Hardware'),
        ('valora', 'Cigo', 'Tabak und E-Zigaretten', 'Tabak'),
        ('e eberhardt', 'E. Eberhardt', 'Tanken und Auto', 'Benzin'),
        ('adac gebaeude', 'ADAC', 'Tanken und Auto', 'Auto ummelden'),
        ('thollembeek', 'Thollembeek', 'Lebensmittel', 'Bäckerei'),
        ('baecker goertz', 'Bäcker Görtz', 'Lebensmittel', 'Bäckerei'),
        ('otantik', 'Otantik', 'Gastronomie und Lieferdienste', 'Imbiss'),
        ('sommer am see', 'Sommer am See', 'Gastronomie und Lieferdienste', 'Essen und Getränke'),
    ]
    changed = 0
    before = conn.execute('SELECT COUNT(*), SUM(amount_cents) FROM transactions').fetchone()
    with conn:
        for row in conn.execute('SELECT * FROM transactions').fetchall():
            if not ('2026-04-01' <= row['booking_date'] <= '2026-08-31') or row['category_status'] == 'Bestätigt':
                continue
            key = normalize_key(row['booking_text'] + ' ' + row['purpose'])
            result = None
            special = None
            if row['amount_cents'] < 0:
                for needle, merchant, category, sub in decisions:
                    if needle in key:
                        result = merchant, category, sub
                        break
                auto = _merchant_and_category(row['booking_text'] + ' ' + row['purpose'], row['amount_cents'])
                if auto[0] in {'Amazon Prime', 'Steam', 'Kinguin', 'Travian Games'}:
                    result = auto[:3]
                elif row['merchant'] == 'Amazon':
                    result = 'Amazon', 'sonstige bestätigte Ausgaben', 'Amazon – nicht aufgeschlüsselt'
            elif row['booking_date'] == '2026-05-05' and row['amount_cents'] == 150000 and 'bundesagentur' in key:
                result = 'Bundesagentur für Arbeit', 'Erstattungen', 'Umzugskostenerstattung'
                special = 'Umzugskostenerstattung'
            elif row['booking_date'] == '2026-05-05' and row['amount_cents'] == 137000 and 'kaution' in key:
                result = row['party'], 'Erstattungen', 'Mietkaution: Teil 1 von 2; Teil 2 steht aus'
                special = 'Kautionsrückzahlung'
            elif row['booking_date'] == '2026-05-15' and row['amount_cents'] == 1312 and 'paypal' in key:
                result = 'Lieferando', 'Erstattungen', 'Bestellerstattung'
                special = 'Erstattung'
            if result:
                conn.execute('UPDATE transactions SET merchant=?, main_category=?, subcategory=?, category_status=?, special_type=? WHERE id=?', (*result, 'Bestätigt', special, row['id']))
                changed += 1
        now = datetime.now().isoformat()
        for key, name, maincat, sub in [('kinguin', 'Kinguin', 'Freizeit, Sport und Kultur', 'Spiele'), ('csc gruene liebe', 'CSC Grüne Liebe', 'Freizeit, Sport und Kultur', 'Cannabisclub-Mitgliedsbeitrag')]:
            conn.execute('INSERT OR IGNORE INTO merchant_rules (merchant_key,display_name,main_category,subcategory,source,confidence,ambiguity,special_type,confirmed_at) VALUES (?,?,?,?,?,?,?,?,?)',
                         (key,name,maincat,sub,'Im Gespräch bestätigt','hoch','Nur dieser Anbieter und dieser bestätigte Zweck',None,now))
        assert tuple(before) == tuple(conn.execute('SELECT COUNT(*), SUM(amount_cents) FROM transactions').fetchone())
        for s in conn.execute('SELECT * FROM statements'):
            total = conn.execute('SELECT SUM(amount_cents) FROM transactions WHERE statement_id=?', (s['id'],)).fetchone()[0]
            assert s['ending_cents'] - s['beginning_cents'] == total
    print('Confirmed assignments:', changed, '; remaining:', conn.execute("SELECT COUNT(*) FROM transactions WHERE main_category='Zu prüfen'").fetchone()[0])
    print('Backup:', backup)
    conn.close()


if __name__ == '__main__':
    main()
