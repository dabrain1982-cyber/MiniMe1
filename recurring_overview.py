"""Conservative summaries of observed recurring payments and income sources."""
from __future__ import annotations

from collections import defaultdict
from datetime import date


OBLIGATION_CATEGORIES = {
    "Wohnen und Energie",
    "Versicherungen und Finanzen",
    "Kommunikation",
    "Abonnements",
}


def _entity(row: dict) -> str:
    merchant = str(row.get("merchant") or "").strip()
    if merchant and merchant != "Nicht eindeutig":
        return merchant
    return str(row.get("party") or row.get("booking_text") or "Nicht eindeutig").strip()


def _rhythm(dates: list[date]) -> str:
    months = sorted({(item.year, item.month) for item in dates})
    if len(months) < 2:
        return "Einmal beobachtet"
    serial = [year * 12 + month for year, month in months]
    gaps = [right - left for left, right in zip(serial, serial[1:])]
    if gaps and max(gaps) <= 1:
        return "Monatlich beobachtet"
    if gaps and all(2 <= gap <= 4 for gap in gaps):
        return "Mehrmonatlich beobachtet"
    return "Unregelmäßig beobachtet"


def _euro(cents: int) -> str:
    return (f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €")


def _summaries(rows: list[dict], *, debit: bool) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        amount = int(row["amount_cents"])
        category = row["main_category"]
        if debit:
            if amount >= 0 or category not in OBLIGATION_CATEGORIES:
                continue
        elif amount <= 0 or category != "Einnahmen":
            continue
        grouped[_entity(row)].append(row)

    output = []
    for name, items in grouped.items():
        dates = [date.fromisoformat(item["booking_date"]) for item in items]
        rhythm = _rhythm(dates)
        if debit and len(items) == 1 and items[0]["main_category"] != "Abonnements":
            continue
        total = sum(abs(int(item["amount_cents"])) for item in items)
        amounts = {abs(int(item["amount_cents"])) for item in items}
        amount_text = _euro(min(amounts)) if len(amounts) == 1 else f"{_euro(min(amounts))} bis {_euro(max(amounts))}"
        output.append({
            "Name": name,
            "Rhythmus": rhythm,
            "Betrag / Spanne": amount_text,
            "Erstmals erfasst": min(dates).strftime("%d.%m.%Y"),
            "Zuletzt erfasst": max(dates).strftime("%d.%m.%Y"),
            "Buchungen": len(items),
            "Bisher": total / 100,
            "Status": "wiederkehrend erkannt" if len({(d.year, d.month) for d in dates}) >= 3 else "Kandidat – noch nicht ausreichend belegt",
        })
    return sorted(output, key=lambda item: item["Bisher"], reverse=True)


def observed_obligations(rows: list[dict]) -> list[dict]:
    return _summaries(rows, debit=True)


def observed_income_sources(rows: list[dict]) -> list[dict]:
    return _summaries(rows, debit=False)
