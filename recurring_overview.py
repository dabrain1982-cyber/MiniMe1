"""Compact, conservative summaries of observed recurring cash flows."""
from __future__ import annotations

from collections import defaultdict
from datetime import date


OBLIGATION_CATEGORIES = {
    "Wohnen und Energie", "Versicherungen und Finanzen", "Kommunikation", "Abonnements",
}
MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _text(row: dict) -> str:
    return " ".join(str(row.get(key) or "") for key in ("merchant", "party", "booking_text", "purpose")).casefold()


def _entity(row: dict) -> str:
    merchant = str(row.get("merchant") or "").strip()
    if merchant and merchant != "Nicht eindeutig":
        return merchant
    return str(row.get("party") or row.get("booking_text") or "Nicht eindeutig").strip()


def _obligation_identity(row: dict) -> tuple[str, str, str, str] | None:
    """Return stable key, human purpose, provider and supported cadence."""
    text = _text(row)
    party = str(row.get("party") or "").strip()
    merchant = str(row.get("merchant") or "").strip()
    rules = (
        (("monatliches entgelt girocard",), ("girocard", "Girocard-Gebühr", "ING", "Monatlich")),
        (("miete ", "miete\n"), ("rent", "Miete", party or merchant, "Monatlich")),
        (("e.on", "abschlag (strom)"), ("electricity", "Strom", "E.ON", "Monatlich")),
        (("telekom", "festnetz vertragskonto"), ("telecom", "Telefon & Internet", "Telekom", "Monatlich")),
        (("hansemerkur", "krankenversicherung"), ("health-insurance", "Krankenversicherung", "HanseMerkur", "Monatlich")),
        (("rundfunk", "beitrags nr."), ("broadcast", "Rundfunkbeitrag", "ARD, ZDF, DRadio", "Vierteljährlich")),
        (("amznprime", "amazon prime"), ("prime", "Prime-Mitgliedschaft", "Amazon", "Jährlich")),
        (("openai",), ("openai", "OpenAI-Abo", "OpenAI", "Monatlich")),
        (("spotify",), ("spotify", "Spotify-Abo", "Spotify", "Monatlich")),
        (("aldi talk",), ("prepaid", "Mobilfunk-Prepaid", "ALDI TALK", "Regelmäßig aufgeladen")),
        (("haftpflicht", "axa"), ("liability-insurance", "Haftpflichtversicherung", "AXA", "Turnus offen")),
        (("kraftfahrt versicherung", "huk-coburg", "huk24"), ("car-insurance", "Kfz-Versicherung", "HUK24", "Turnus offen")),
        (("mieterverein",), ("tenant-association", "Mieterverein-Mitgliedschaft", party or merchant or "Mieterverein", "Turnus offen")),
    )
    for needles, identity in rules:
        if any(needle in text for needle in needles):
            if identity[0] == "rent" and "mieterverein" in text:
                continue
            return identity
    return None


def _rhythm(dates: list[date]) -> str:
    months = sorted({(item.year, item.month) for item in dates})
    if len(months) < 2:
        return "Turnus offen"
    serial = [year * 12 + month for year, month in months]
    gaps = [right - left for left, right in zip(serial, serial[1:])]
    if gaps and max(gaps) <= 1:
        return "Monatlich beobachtet"
    if gaps and all(2 <= gap <= 4 for gap in gaps):
        return "Mehrmonatlich beobachtet"
    return "Unregelmäßig beobachtet"


def _euro(cents: int) -> str:
    return f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _first_seen(value: date) -> str:
    return f"seit {MONTHS[value.month - 1]} {value.year} erfasst"


def _amount_label(items: list[dict], cadence: str) -> str:
    amounts = [abs(int(item["amount_cents"])) for item in sorted(items, key=lambda item: item["booking_date"])]
    suffix = {"Monatlich": "/Monat", "Vierteljährlich": "/Quartal", "Jährlich": "/Jahr", "Regelmäßig aufgeladen": "/Aufladung"}.get(cadence, "")
    if len(amounts) >= 2 and amounts[-1] == amounts[-2]:
        return f"{_euro(amounts[-1])}{suffix}"
    if min(amounts) != max(amounts):
        return f"{_euro(min(amounts))}–{_euro(max(amounts))}{suffix}"
    return f"{_euro(amounts[0])}{suffix}"


def observed_obligations(rows: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}
    fallback: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if int(row["amount_cents"]) >= 0 or row["main_category"] not in OBLIGATION_CATEGORIES:
            continue
        identity = _obligation_identity(row)
        if identity:
            key, kind, provider, cadence = identity
            group = grouped.setdefault(key, {"Art": kind, "Anbieter": provider, "Rhythmus": cadence, "items": []})
            group["items"].append(row)
        else:
            fallback[_entity(row)].append(row)
    for name, items in fallback.items():
        if len(items) >= 2:
            grouped[f"fallback:{name}"] = {
                "Art": str(items[0].get("main_category") or "Laufende Zahlung"),
                "Anbieter": name,
                "Rhythmus": _rhythm([date.fromisoformat(item["booking_date"]) for item in items]),
                "items": items,
            }
    output = []
    for group in grouped.values():
        items = group.pop("items")
        dates = [date.fromisoformat(item["booking_date"]) for item in items]
        total = sum(abs(int(item["amount_cents"])) for item in items)
        output.append({**group, "Betrag": _amount_label(items, group["Rhythmus"]), "Erfasst seit": _first_seen(min(dates)), "Bisher": total / 100})
    return sorted(output, key=lambda item: item["Bisher"], reverse=True)


def observed_income_sources(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if int(row["amount_cents"]) > 0 and row["main_category"] == "Einnahmen":
            grouped[_entity(row)].append(row)
    output = []
    for provider, items in grouped.items():
        dates = [date.fromisoformat(item["booking_date"]) for item in items]
        is_salary = any("lohn" in _text(item) or "gehalt" in _text(item) for item in items)
        rhythm = "Monatlich" if is_salary and len({(item.year, item.month) for item in dates}) >= 2 else _rhythm(dates)
        total = sum(int(item["amount_cents"]) for item in items)
        output.append({
            "Art": "Gehalt" if is_salary else "Einnahme",
            "Anbieter": provider,
            "Rhythmus": rhythm,
            "Betrag": _amount_label(items, rhythm),
            "Erfasst seit": _first_seen(min(dates)),
            "Bisher": total / 100,
        })
    return sorted(output, key=lambda item: item["Bisher"], reverse=True)
