from __future__ import annotations

import hashlib
import io
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator

from pypdf import PdfReader


MAIN_CATEGORIES = [
    "Tabak und E-Zigaretten",
    "Wohnen und Energie",
    "Lebensmittel",
    "Gastronomie und Lieferdienste",
    "Tanken und Auto",
    "Mobilität",
    "Gesundheit",
    "Versicherungen und Finanzen",
    "Kommunikation",
    "Freizeit, Sport und Kultur",
    "Haushalt und Anschaffungen",
    "Abonnements",
    "Einnahmen",
    "Erstattungen",
    "interne Umbuchungen",
    "sonstige bestätigte Ausgaben",
    "Zu prüfen",
]

INTERNAL_CATEGORY = "interne Umbuchungen"
REFUND_CATEGORY = "Erstattungen"
REVIEW_CATEGORY = "Zu prüfen"


class ParseError(ValueError):
    """A safe, user-facing PDF parsing error."""


class PeriodParseError(ParseError):
    """The statement period needs manual confirmation."""


@dataclass
class ParsedTransaction:
    booking_date: str
    value_date: str | None
    party: str
    booking_text: str
    purpose: str
    amount_cents: int
    direction: str
    currency: str
    main_category: str
    subcategory: str
    merchant: str
    category_status: str
    special_type: str | None = None
    fingerprint: str = ""


@dataclass
class ParsedStatement:
    file_hash: str
    filename: str
    account_token: str
    account_masked: str
    period_start: str
    period_end: str
    beginning_cents: int
    ending_cents: int
    currency: str
    transactions: list[ParsedTransaction] = field(default_factory=list)
    reconciliation_diff_cents: int = 0
    confirmed: bool = False
    warnings: list[str] = field(default_factory=list)


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    return re.sub(r"\s+", " ", value).strip()


def normalize_key(value: str) -> str:
    value = normalize_text(value).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def money_to_cents(number: str, sign: int = 1) -> int:
    clean = number.replace(".", "").replace(" ", "").replace(",", ".")
    return int(round(float(clean) * 100)) * sign


AMOUNT_TOKEN = r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}"
AMOUNT_RE = re.compile(
    rf"(?P<prefix>[+\-−])?\s*(?P<number>{AMOUNT_TOKEN})\s*(?P<suffix>[+\-−]|S|H)?\s*(?:EUR|€)?\s*$",
    re.IGNORECASE,
)
SHORT_OR_FULL_DATE = r"\d{2}\.\d{2}\.(?:\d{2,4})?"
DATE_RE = re.compile(
    rf"^(?P<book>{SHORT_OR_FULL_DATE})(?:\s+(?P<value>{SHORT_OR_FULL_DATE}))?\s+"
)


def _signed_amount(match: re.Match[str], context: str, *, balance: bool = False) -> int:
    prefix = (match.group("prefix") or "").upper().replace("−", "-")
    suffix = (match.group("suffix") or "").upper().replace("−", "-")
    if prefix == "-" or suffix in {"-", "S"}:
        sign = -1
    elif prefix == "+" or suffix in {"+", "H"}:
        sign = 1
    elif balance:
        sign = 1
    else:
        key = normalize_key(context)
        debit_markers = (
            "lastschrift",
            "kartenzahlung",
            "entgelt",
            "abbuchung",
            "geldautomat",
            "barabhebung",
            "kreditkartenabrechnung",
        )
        credit_markers = ("gutschrift", "gehalt", "lohn", "rueckerstattung", "erstattung")
        if any(marker in key for marker in debit_markers):
            sign = -1
        elif any(marker in key for marker in credit_markers):
            sign = 1
        else:
            raise ParseError(
                "Mindestens ein Buchungsbetrag hat kein eindeutig erkennbares Soll-/Haben-Vorzeichen. "
                "Der Import wurde vorsichtshalber nicht freigegeben."
            )
    return money_to_cents(match.group("number"), sign)


def _parse_date(raw: str, period_start: date, period_end: date) -> date:
    parts = raw.split(".")
    day, month = int(parts[0]), int(parts[1])
    if len(parts) >= 3 and parts[2]:
        year = int(parts[2])
        if year < 100:
            year += 2000
    else:
        year = period_start.year
        candidate = date(year, month, day)
        if candidate < period_start and period_end.year > period_start.year:
            year = period_end.year
    return date(year, month, day)


def _date_tokens(value: str) -> list[date]:
    found: list[date] = []
    for raw in re.findall(r"\b\d{2}\.\d{2}\.\d{2,4}\b", value):
        try:
            found.append(_full_date(raw))
        except ParseError:
            continue
    return found


def _find_period(text: str, lines: list[str]) -> tuple[date, date]:
    patterns = [
        r"(?:Abrechnungszeitraum|Zeitraum|Auszugszeitraum)\s*:?\s*(\d{2}\.\d{2}\.\d{2,4})\s*(?:bis|[-–])\s*(\d{2}\.\d{2}\.\d{2,4})",
        r"vom\s+(\d{2}\.\d{2}\.\d{2,4})\s+bis\s+(\d{2}\.\d{2}\.\d{2,4})",
        r"von\s+(\d{2}\.\d{2}\.\d{2,4})\s+bis\s+(\d{2}\.\d{2}\.\d{2,4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return _full_date(match.group(1)), _full_date(match.group(2))

    month_match = re.search(
        r"(?:Kontoauszug|Monatsauszug|Auszug)\s*(?:Nr\.?\s*\d+\s*)?"
        r"(0?[1-9]|1[0-2])\s*[/.-]\s*(20\d{2})",
        text,
        re.IGNORECASE,
    )
    if month_match:
        month = int(month_match.group(1))
        year = int(month_match.group(2))
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])

    opening_date: date | None = None
    closing_date: date | None = None
    opening_is_prior_balance = False
    for line in lines:
        key = normalize_key(line)
        dates = _date_tokens(line)
        if not dates:
            continue
        if any(marker in key for marker in ("neuer kontostand", "endsaldo", "saldo am ende", "kontostand zum")):
            closing_date = dates[-1]
        elif any(marker in key for marker in ("alter kontostand", "kontostand vom", "saldo bisher")):
            opening_date = dates[-1]
            opening_is_prior_balance = True
        elif any(marker in key for marker in ("anfangssaldo", "saldo am anfang")):
            opening_date = dates[-1]
            opening_is_prior_balance = False
    if opening_date and closing_date:
        period_start = opening_date + timedelta(days=1) if opening_is_prior_balance else opening_date
        if period_start <= closing_date:
            return period_start, closing_date
    booking_period = _period_from_booking_dates(lines)
    if booking_period:
        return booking_period
    raise PeriodParseError(
        "Der Zeitraum lässt sich aus den Buchungsdaten und den Angaben im Auszug nicht eindeutig ableiten."
    )


def _period_from_booking_dates(lines: list[str]) -> tuple[date, date] | None:
    """Infer the monthly reporting window from booking dates, never value dates."""
    raw_dates: list[str] = []
    header_years: set[int] = set()
    balance_markers = ("saldo", "kontostand")
    for line in lines:
        key = normalize_key(line)
        match = DATE_RE.match(line)
        if match and not any(marker in key for marker in balance_markers):
            raw_dates.append(match.group("book"))
        elif any(marker in key for marker in ("kontoauszug", "auszugsdatum", "erstellt am", "datum")):
            header_years.update(int(y) for y in re.findall(r"\b20\d{2}\b", line))
    if not raw_dates:
        return None
    full_dates = [_full_date(raw) for raw in raw_dates if raw.split(".")[2]]
    years = {item.year for item in full_dates} or header_years
    if len(years) != 1:
        return None
    year = next(iter(years))
    try:
        dates = [_parse_date(raw, date(year, 1, 1), date(year, 12, 31)) for raw in raw_dates]
    except ValueError:
        return None
    months = {(item.year, item.month) for item in dates}
    if len(months) != 1:
        return None
    year, month = next(iter(months))
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _full_date(raw: str) -> date:
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    raise ParseError(f"Das Datum „{raw}“ ist nicht lesbar.")


def _find_account(text: str) -> tuple[str, str]:
    iban_match = re.search(r"\b(DE\d{2}(?:\s?\d){18})\b", text, re.IGNORECASE)
    if not iban_match:
        iban_match = re.search(r"\b([A-Z]{2}\d{2}[A-Z0-9]{11,30})\b", text, re.IGNORECASE)
    if iban_match:
        raw = re.sub(r"\s+", "", iban_match.group(1)).upper()
        token = hashlib.sha256(("iban:" + raw).encode("utf-8")).hexdigest()
        return token, f"{raw[:2]}•• •••• •••• {raw[-4:]}"
    account_match = re.search(
        r"(?:Kontonummer|Konto-Nr\.?|Konto)\s*:?\s*([0-9][0-9\s-]{5,})",
        text,
        re.IGNORECASE,
    )
    if account_match:
        raw = re.sub(r"\D", "", account_match.group(1))
        token = hashlib.sha256(("account:" + raw).encode("utf-8")).hexdigest()
        return token, f"Konto •••• {raw[-4:]}"
    raise ParseError(
        "Das Konto konnte nicht sicher identifiziert werden. Ohne maskierbare IBAN oder Kontonummer "
        "wird der Import nicht gestartet."
    )


def _find_balance(lines: list[str], start: bool) -> int:
    if start:
        markers = ("anfangssaldo", "alter kontostand", "saldo am anfang", "kontostand vom")
        label = "Anfangssaldo"
    else:
        markers = ("endsaldo", "neuer kontostand", "saldo am ende", "kontostand zum")
        label = "Endsaldo"
    candidates: list[int] = []
    for line in lines:
        key = normalize_key(line)
        if any(marker in key for marker in markers):
            match = AMOUNT_RE.search(line)
            if match:
                candidates.append(_signed_amount(match, line, balance=True))
    if not candidates:
        raise ParseError(f"Der {label} fehlt oder konnte nicht zuverlässig gelesen werden.")
    return candidates[0] if start else candidates[-1]


def _merchant_and_category(
    raw_description: str,
    amount_cents: int,
    merchant_rules: dict[str, dict[str, str]] | None = None,
) -> tuple[str, str, str, str, str | None]:
    text = normalize_text(raw_description)
    key = normalize_key(text)
    # Mandate/reference identifiers are evidence for duplicates, not category keywords.
    key = re.split(r"\b(?:mandat|referenz)\b", key)[0]
    merchant_rules = merchant_rules or {}
    compact = re.sub(r"\s+", "", key)
    if amount_cents < 0:
        if "amznprime" in compact:
            return "Amazon Prime", "Abonnements", "Amazon Prime", "Automatisch", None
        if "kinguin" in compact:
            return "Kinguin", "Freizeit, Sport und Kultur", "Spiele", "Bestätigt", None
        if "steampowered" in compact or "traviangames" in compact:
            return ("Steam" if "steampowered" in compact else "Travian Games"), "Freizeit, Sport und Kultur", "Spiele", "Automatisch", None

    known_merchants = [
        (r"\bspotify\b", "Spotify"),
        (r"\bopenai\b|\bope nai\b", "OpenAI"),
        (r"\btakeaway\b", "Lieferando"),
        (r"\be plus\b|\baldi ta lk\b", "Aldi Talk"),
        (r"\bmcdonalds\b", "McDonald's"),
        (r"\bkaufland\b", "Kaufland"),
        (r"\btedi\b", "TEDi"),
        (r"\bshell\b", "Shell"),
        (r"\btelekom\b", "Telekom"),
        (r"\bhansemerkur\b", "HanseMerkur"),
        (r"\be on\b", "E.ON"),
        (r"\baldi\b", "Aldi"),
        (r"\blidl\b", "Lidl"),
        (r"\brewe\b", "Rewe"),
        (r"\bedeka\b", "Edeka"),
        (r"\bpenny\b", "Penny"),
        (r"\bnetto\b", "Netto"),
        (r"\bdm\b", "dm"),
        (r"\brossmann\b", "Rossmann"),
        (r"\bamazon\b", "Amazon"),
        (r"\bpaypal\b", "PayPal"),
    ]
    merchant = "Nicht eindeutig"
    for pattern, name in known_merchants:
        if re.search(pattern, key):
            merchant = name
            break

    for rule_key, rule in merchant_rules.items():
        if rule_key and rule_key in key:
            return (
                rule.get("display_name", merchant),
                rule["main_category"],
                rule["subcategory"],
                "Bestätigt",
                rule.get("special_type"),
            )

    def result(main: str, sub: str, status: str = "Automatisch", special: str | None = None):
        return merchant, main, sub, status, special

    if any(word in key for word in ("eigenuebertrag", "umbuchung", "tagesgeld", "sparkonto", "sparuebertrag")):
        return result(INTERNAL_CATEGORY, "Eigene Konten", special="Interne Umbuchung")
    if any(word in key for word in ("rueckerstattung", "erstattung", "retoure", "ruecklastschrift")):
        return result(REFUND_CATEGORY, "Erstattung oder Rückbuchung", special="Erstattung")
    if any(word in key for word in ("geldautomat", "barabhebung", "bargeldauszahlung")):
        return "Geldautomat", REVIEW_CATEGORY, "Bargeldabhebung", "Zu prüfen", "Bargeldabhebung"
    if any(word in key for word in ("kreditkartenabrechnung", "kreditkartenausgleich")):
        return result("Versicherungen und Finanzen", "Kreditkartenausgleich", special="Kreditkartenausgleich")
    if amount_cents > 0 and any(word in key for word in ("gehalt", "lohn", "rente", "bezuege")):
        return result("Einnahmen", "Gehalt, Lohn oder Bezüge")
    if amount_cents > 0:
        return result(REVIEW_CATEGORY, "Unklare Gutschrift", "Zu prüfen")
    if merchant == "Amazon":
        return result("sonstige bestätigte Ausgaben", "Amazon – nicht aufgeschlüsselt", "Bestätigt")
    if merchant == "Aldi Talk":
        return result("Kommunikation", "Prepaid-Mobilfunk")
    if merchant in {"Spotify", "OpenAI"}:
        return result("Abonnements", "Digitaler Dienst; Tarif nicht geprüft")
    if merchant in {"McDonald's", "Lieferando"}:
        return result("Gastronomie und Lieferdienste", "Restaurant oder Lieferdienst")
    if "mieterverein" in key:
        return result("Wohnen und Energie", "Mieterverein")
    if "rundfunk" in key:
        return result("Wohnen und Energie", "Rundfunkbeitrag")
    if "monatliches entgelt girocard" in key:
        return result("Versicherungen und Finanzen", "Kartengebühr")
    if "tierarzt" in key:
        return result("Gesundheit", "Tierarzt")
    if merchant in {"TEDi"} or "baumarkt" in key:
        return result("Haushalt und Anschaffungen", "Haushalt oder Baumarkt")
    if merchant in {"Aldi", "Lidl", "Rewe", "Edeka", "Penny", "Netto", "Kaufland"}:
        return result("Lebensmittel", "Supermarkt")
    if merchant in {"dm", "Rossmann"}:
        return result("Haushalt und Anschaffungen", "Drogerie")
    if any(word in key for word in ("miete", "vermieter", "nebenkosten", "stadtwerke", "strom", "gasabschlag")):
        return result("Wohnen und Energie", "Miete, Nebenkosten oder Energie")
    if any(word in key for word in ("tankstelle", "shell", "aral", "esso", "totalenergies", "werkstatt")):
        return result("Tanken und Auto", "Kraftstoff oder Werkstatt")
    if any(re.search(r"\b" + word + r"\b", key) for word in ("deutsche bahn", "db vertrieb", "verkehrsverbund", "taxi", "uber")):
        return result("Mobilität", "ÖPNV, Bahn oder Taxi")
    if any(word in key for word in ("apotheke", "arzt", "zahnarzt", "therapie")):
        return result("Gesundheit", "Apotheke oder Behandlung")
    if any(word in key for word in ("versicherung", "krankenkasse", "kontofuehrung", "bankentgelt")):
        return result("Versicherungen und Finanzen", "Versicherung oder Bankentgelt")
    if any(word in key for word in ("telekom", "vodafone", "telefonica", "o2", "internet")):
        return result("Kommunikation", "Telefon oder Internet")
    if any(word in key for word in ("netflix", "spotify", "disney", "prime video", "abo ")):
        return result("Abonnements", "Digitales Abonnement")
    if any(word in key for word in ("restaurant", "lieferando", "doordash", "wolt", "cafe", "bistro")):
        return result("Gastronomie und Lieferdienste", "Restaurant oder Lieferdienst")
    if any(word in key for word in ("kino", "fitness", "verein", "theater", "museum")):
        return result("Freizeit, Sport und Kultur", "Freizeit, Sport oder Kultur")
    if amount_cents > 0:
        return merchant, REVIEW_CATEGORY, "Unklare Gutschrift", "Zu prüfen", None
    return merchant, REVIEW_CATEGORY, "Unklare Ausgabe", "Zu prüfen", None


def _extract_transactions(
    lines: list[str],
    period_start: date,
    period_end: date,
    account_token: str,
    currency: str,
    merchant_rules: dict[str, dict[str, str]] | None,
) -> list[ParsedTransaction]:
    buffers: list[list[str]] = []
    current: list[str] | None = None
    for original in lines:
        line = normalize_text(original)
        if not line:
            continue
        line_key = normalize_key(line)
        is_balance_line = any(
            marker in line_key
            for marker in (
                "anfangssaldo",
                "alter kontostand",
                "saldo am anfang",
                "endsaldo",
                "neuer kontostand",
                "saldo am ende",
            )
        )
        if DATE_RE.match(line) or is_balance_line:
            if current:
                buffers.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current:
        buffers.append(current)

    transactions: list[ParsedTransaction] = []
    for buffer in buffers:
        joined = " ".join(buffer)
        joined_key = normalize_key(joined)
        if any(
            marker in joined_key
            for marker in (
                "anfangssaldo",
                "alter kontostand",
                "saldo am anfang",
                "endsaldo",
                "neuer kontostand",
                "saldo am ende",
            )
        ):
            continue
        date_match = DATE_RE.match(joined)
        amount_match = AMOUNT_RE.search(joined)
        if not date_match or not amount_match:
            continue
        booking_date = _parse_date(date_match.group("book"), period_start, period_end)
        if booking_date < period_start or booking_date > period_end:
            continue
        value_date = (
            _parse_date(date_match.group("value"), period_start, period_end)
            if date_match.group("value")
            else None
        )
        amount_cents = _signed_amount(amount_match, joined)
        description = joined[date_match.end() : amount_match.start()].strip(" -–|;")
        description = normalize_text(description)
        if not description:
            description = "Buchung ohne lesbaren Text"
        booking_text, purpose = _split_description(description)
        merchant, main, sub, status, special = _merchant_and_category(
            description, amount_cents, merchant_rules
        )
        fingerprint_input = "|".join(
            [
                account_token,
                booking_date.isoformat(),
                value_date.isoformat() if value_date else "",
                str(amount_cents),
                normalize_key(description),
            ]
        )
        transactions.append(
            ParsedTransaction(
                booking_date=booking_date.isoformat(),
                value_date=value_date.isoformat() if value_date else None,
                party=merchant if merchant != "Nicht eindeutig" else booking_text[:100],
                booking_text=booking_text[:500],
                purpose=purpose[:1000],
                amount_cents=amount_cents,
                direction="Haben" if amount_cents > 0 else "Soll",
                currency=currency,
                main_category=main,
                subcategory=sub,
                merchant=merchant,
                category_status=status,
                special_type=special,
                fingerprint=hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest(),
            )
        )
    if not transactions:
        raise ParseError(
            "Es wurden keine zuverlässig lesbaren Buchungszeilen gefunden. Bei einem Scan ist OCR nötig; "
            "bei einer Text-PDF wird ein bankspezifisches Importprofil benötigt."
        )
    return transactions


def _split_description(description: str) -> tuple[str, str]:
    match = re.search(r"\b(?:Verwendungszweck|VWZ|Referenz)\b\s*:?", description, re.IGNORECASE)
    if not match:
        return description[:500], ""
    return description[: match.start()].strip(), description[match.end() :].strip()


def parse_statement_pdf(
    data: bytes,
    filename: str,
    merchant_rules: dict[str, dict[str, str]] | None = None,
    period_override: tuple[date, date] | None = None,
) -> ParsedStatement:
    if not data.startswith(b"%PDF"):
        raise ParseError("Die Datei ist keine erkennbare PDF-Datei.")
    file_hash = sha256_bytes(data)
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise ParseError("Die PDF konnte nicht gelesen werden. Sie ist eventuell beschädigt oder geschützt.") from exc
    text = "\n".join(pages)
    if "ING-DiBa AG" in text and re.search(r"Girokonto Nummer \d+", text):
        text = _normalize_ing_statement(pages)
    if len(normalize_text(text)) < 80:
        raise ParseError(
            "Die PDF enthält keinen ausreichend zuverlässigen Text. Ein reiner Scan wird ohne geprüfte OCR "
            "nicht importiert."
        )
    lines = [normalize_text(line) for line in text.splitlines() if normalize_text(line)]
    account_token, account_masked = _find_account(text)
    if period_override:
        period_start, period_end = period_override
        if period_start > period_end:
            raise ParseError("Der manuell bestätigte Zeitraum endet vor seinem Anfang.")
    else:
        period_start, period_end = _find_period(text, lines)
    beginning_cents = _find_balance(lines, start=True)
    ending_cents = _find_balance(lines, start=False)
    currency_match = re.search(r"\b(EUR|USD|CHF|GBP)\b|€", text, re.IGNORECASE)
    if not currency_match:
        raise ParseError("Die Währung konnte nicht sicher erkannt werden.")
    currency = "EUR" if currency_match.group(0) == "€" else currency_match.group(1).upper()
    transactions = _extract_transactions(
        lines, period_start, period_end, account_token, currency, merchant_rules
    )
    for item in transactions:
        item.party = re.sub(r"^(?:Lastschrift|Gutschrift|Gehalt/Rente|Entgelt|Dauerauftrag/Terminueberw\.|Echtzeitüberweisung)\s+", "", item.booking_text)
    transaction_sum = sum(item.amount_cents for item in transactions)
    diff = ending_cents - beginning_cents - transaction_sum
    warnings: list[str] = []
    if diff:
        warnings.append(
            "Die Saldoformel geht nicht cent-genau auf. Mögliche Ursachen sind eine fehlende Buchung, "
            "eine falsch erkannte Soll-/Haben-Richtung oder ein mehrzeiliger PDF-Eintrag."
        )
    if any(item.main_category == REVIEW_CATEGORY for item in transactions):
        warnings.append("Mindestens eine Buchung benötigt eine manuelle Kategorieprüfung.")
    return ParsedStatement(
        file_hash=file_hash,
        filename=Path(filename).name,
        account_token=account_token,
        account_masked=account_masked,
        period_start=period_start.isoformat(),
        period_end=period_end.isoformat(),
        beginning_cents=beginning_cents,
        ending_cents=ending_cents,
        currency=currency,
        transactions=transactions,
        reconciliation_diff_cents=diff,
        confirmed=diff == 0,
        warnings=warnings,
    )


def _normalize_ing_statement(pages: list[str]) -> str:
    """Read the ING two-line booking/valuta layout, excluding page furniture."""
    text = "\n".join(pages)
    pagination = re.findall(r"Seite (\d+) von (\d+)", text)
    if pagination:
        totals = {int(total) for _, total in pagination}
        if len(totals) != 1 or {int(n) for n, _ in pagination} != set(range(1, next(iter(totals)) + 1)):
            raise ParseError("Im ING-Auszug fehlen Seiten oder die Seitennummern widersprechen sich.")
    months = "Januar Februar März April Mai Juni Juli August September Oktober November Dezember".split()
    header = re.search(r"Kontoauszug (\w+) (20\d{2})", text)
    if not header or header[1] not in months:
        raise ParseError("Das ING-Auszugdatum ist nicht lesbar.")
    month, year = months.index(header[1]) + 1, int(header[2])
    iban = re.search(r"IBAN\s+(DE\d{2}(?:\s?\d){18})", text)
    if not iban:
        raise ParseError("Die ING-Kontoidentifikation fehlt.")
    balances = []
    for label in ("Alter", "Neuer"):
        found = re.findall(rf"{label} Saldo\s+(-?(?:{AMOUNT_TOKEN}))", text)
        if not found or len(set(found)) != 1:
            raise ParseError("Die ING-Saldoangaben fehlen oder widersprechen sich.")
        balances.append(found[0])
    output = [f"IBAN {iban[1]}", f"Abrechnungszeitraum 01.{month:02}.{year} - {monthrange(year, month)[1]:02}.{month:02}.{year}",
              f"Anfangssaldo {balances[0]} EUR"]
    start_re = re.compile(rf"^(\d{{2}}\.\d{{2}}\.\d{{4}})\s+(.+?)\s+(-?(?:{AMOUNT_TOKEN}))$")
    current = None
    rows = []
    for page in pages:
        if "Buchung Buchung / Verwendungszweck" not in page:
            continue
        for raw in page.splitlines():
            line = normalize_text(raw)
            if re.match(r"\d*GKKA\d+", line) or line.startswith("Neuer Saldo"):
                break
            match = start_re.match(line)
            if match:
                if current:
                    rows.append(current)
                current = [match[1], None, match[2], match[3], []]
            elif current and re.match(r"^\d{2}\.\d{2}\.\d{4}(?:\s|$)", line):
                value, _, rest = line.partition(" ")
                if current[1] is not None:
                    raise ParseError("Unerwartete zusätzliche Datumszeile im ING-Auszug.")
                current[1] = value
                current[4].append(rest)
            elif current and not line.startswith(("Buchung Buchung", "Valuta", "Girokonto Nummer", "Kontoauszug ", "Datum ", "Seite ")):
                current[4].append(line)
        # Legal-information pages carry no booking table.
        if "Bitte beachten Sie die nachstehenden Hinweise:" in page:
            break
    if current:
        rows.append(current)
    for booking, value, description, amount, details in rows:
        if not value:
            raise ParseError("Eine ING-Buchung hat keine lesbare Wertstellung.")
        when = _full_date(booking)
        if (when.year, when.month) != (year, month):
            raise ParseError("Eine ING-Buchung liegt außerhalb des Auszugsmonats.")
        # ING prints credits without a plus sign, debits with a minus sign.
        signed = amount if amount.startswith("-") else "+" + amount
        output.append(f"{booking} {value} {description} Verwendungszweck: {' '.join(details)} {signed} EUR")
    output.append(f"Endsaldo {balances[1]} EUR")
    return "\n".join(output)


@contextmanager
def connect_db(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db(db_path: Path) -> None:
    with connect_db(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS statements (
                id INTEGER PRIMARY KEY,
                file_hash TEXT NOT NULL UNIQUE,
                source_filename TEXT NOT NULL,
                account_token TEXT NOT NULL,
                account_masked TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                beginning_cents INTEGER NOT NULL,
                ending_cents INTEGER NOT NULL,
                currency TEXT NOT NULL,
                reconciliation_diff_cents INTEGER NOT NULL,
                confirmed INTEGER NOT NULL,
                tx_count_extracted INTEGER NOT NULL,
                tx_count_imported INTEGER NOT NULL,
                imported_at TEXT NOT NULL,
                UNIQUE(account_token, period_start, period_end)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY,
                statement_id INTEGER NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
                account_token TEXT NOT NULL,
                fingerprint TEXT NOT NULL UNIQUE,
                booking_date TEXT NOT NULL,
                value_date TEXT,
                party TEXT NOT NULL,
                booking_text TEXT NOT NULL,
                purpose TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                direction TEXT NOT NULL,
                currency TEXT NOT NULL,
                main_category TEXT NOT NULL,
                subcategory TEXT NOT NULL,
                merchant TEXT NOT NULL,
                category_status TEXT NOT NULL,
                special_type TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS merchant_rules (
                merchant_key TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                main_category TEXT NOT NULL,
                subcategory TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence TEXT NOT NULL,
                ambiguity TEXT NOT NULL,
                special_type TEXT,
                confirmed_at TEXT NOT NULL
            );
            """
        )


def get_merchant_rules(db_path: Path) -> dict[str, dict[str, str]]:
    with connect_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM merchant_rules").fetchall()
    return {row["merchant_key"]: dict(row) for row in rows}


def existing_statement(db_path: Path, file_hash: str) -> dict[str, Any] | None:
    with connect_db(db_path) as conn:
        row = conn.execute("SELECT * FROM statements WHERE file_hash = ?", (file_hash,)).fetchone()
    return dict(row) if row else None


def current_account_token(db_path: Path) -> str | None:
    with connect_db(db_path) as conn:
        row = conn.execute("SELECT account_token FROM statements ORDER BY id LIMIT 1").fetchone()
    return row[0] if row else None


def import_statement(db_path: Path, parsed: ParsedStatement) -> dict[str, int | bool]:
    difference = parsed.ending_cents - parsed.beginning_cents - sum(t.amount_cents for t in parsed.transactions)
    if difference or not parsed.confirmed:
        raise ParseError("Der Auszug ist nicht cent-genau abgestimmt und kann noch nicht freigegeben werden.")
    if existing_statement(db_path, parsed.file_hash):
        return {"duplicate": True, "statement_id": 0, "imported": 0, "overlap_duplicates": 0}
    expected = current_account_token(db_path)
    if expected and expected != parsed.account_token:
        raise ParseError("Dieser Kontoauszug gehört nicht zu dem bereits angelegten Konto. Der Import wurde gestoppt.")
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with connect_db(db_path) as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO statements (
                    file_hash, source_filename, account_token, account_masked, period_start, period_end,
                    beginning_cents, ending_cents, currency, reconciliation_diff_cents, confirmed,
                    tx_count_extracted, tx_count_imported, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                """,
                (
                    parsed.file_hash,
                    parsed.filename,
                    parsed.account_token,
                    parsed.account_masked,
                    parsed.period_start,
                    parsed.period_end,
                    parsed.beginning_cents,
                    parsed.ending_cents,
                    parsed.currency,
                    parsed.reconciliation_diff_cents,
                    int(parsed.confirmed),
                    len(parsed.transactions),
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ParseError("Für dieses Konto und diesen Abrechnungszeitraum ist bereits ein Auszug gespeichert.") from exc
        statement_id = int(cursor.lastrowid)
        imported = 0
        overlap = 0
        for item in parsed.transactions:
            try:
                conn.execute(
                    """
                    INSERT INTO transactions (
                        statement_id, account_token, fingerprint, booking_date, value_date, party,
                        booking_text, purpose, amount_cents, direction, currency, main_category,
                        subcategory, merchant, category_status, special_type, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        statement_id,
                        parsed.account_token,
                        item.fingerprint,
                        item.booking_date,
                        item.value_date,
                        item.party,
                        item.booking_text,
                        item.purpose,
                        item.amount_cents,
                        item.direction,
                        item.currency,
                        item.main_category,
                        item.subcategory,
                        item.merchant,
                        item.category_status,
                        item.special_type,
                        now,
                    ),
                )
                imported += 1
            except sqlite3.IntegrityError:
                overlap += 1
        conn.execute(
            "UPDATE statements SET tx_count_imported = ? WHERE id = ?",
            (imported, statement_id),
        )
    return {
        "duplicate": False,
        "statement_id": statement_id,
        "imported": imported,
        "overlap_duplicates": overlap,
    }


def load_statements(db_path: Path) -> list[dict[str, Any]]:
    with connect_db(db_path) as conn:
        rows = conn.execute("SELECT * FROM statements ORDER BY period_start, id").fetchall()
    return [dict(row) for row in rows]


def load_transactions(db_path: Path, statement_id: int | None = None) -> list[dict[str, Any]]:
    query = "SELECT * FROM transactions"
    params: tuple[Any, ...] = ()
    if statement_id is not None:
        query += " WHERE statement_id = ?"
        params = (statement_id,)
    query += " ORDER BY booking_date DESC, id DESC"
    with connect_db(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def save_transaction_corrections(db_path: Path, rows: Iterable[dict[str, Any]]) -> int:
    updated = 0
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with connect_db(db_path) as conn:
        for row in rows:
            transaction_id = int(row["id"])
            current = conn.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
            if not current:
                continue
            main = str(row["main_category"])
            sub = normalize_text(str(row["subcategory"])) or "Nicht näher zugeordnet"
            merchant = normalize_text(str(row["merchant"])) or "Nicht eindeutig"
            if main not in MAIN_CATEGORIES:
                main = REVIEW_CATEGORY
            changed = (
                main != current["main_category"]
                or sub != current["subcategory"]
                or merchant != current["merchant"]
            )
            if not changed:
                continue
            status = "Bestätigt" if main != REVIEW_CATEGORY else "Zu prüfen"
            conn.execute(
                """
                UPDATE transactions
                SET main_category = ?, subcategory = ?, merchant = ?, category_status = ?
                WHERE id = ?
                """,
                (main, sub, merchant, status, transaction_id),
            )
            if merchant != "Nicht eindeutig" and main != REVIEW_CATEGORY:
                merchant_key = normalize_key(merchant)
                if merchant_key:
                    conn.execute(
                        """
                        INSERT INTO merchant_rules (
                            merchant_key, display_name, main_category, subcategory, source,
                            confidence, ambiguity, special_type, confirmed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(merchant_key) DO UPDATE SET
                            display_name=excluded.display_name,
                            main_category=excluded.main_category,
                            subcategory=excluded.subcategory,
                            source=excluded.source,
                            confidence=excluded.confidence,
                            ambiguity=excluded.ambiguity,
                            confirmed_at=excluded.confirmed_at
                        """,
                        (
                            merchant_key,
                            merchant,
                            main,
                            sub,
                            "Manuell vom Kontoinhaber bestätigt",
                            "hoch",
                            "Gilt für künftig eindeutig erkannte Händlerbezeichnungen",
                            current["special_type"],
                            now,
                        ),
                    )
            updated += 1
    return updated


def aggregate_amounts(transactions: Iterable[dict[str, Any]]) -> dict[str, int]:
    income = expenses = refunds = internal = review = 0
    total_movement = 0
    for row in transactions:
        amount = int(row["amount_cents"])
        category = row["main_category"]
        total_movement += amount
        if category == INTERNAL_CATEGORY:
            internal += amount
        elif category == REFUND_CATEGORY and amount > 0:
            refunds += amount
        elif amount > 0 and category != REVIEW_CATEGORY:
            income += amount
        elif amount < 0:
            expenses += -amount
        if category == REVIEW_CATEGORY:
            review += 1
    return {
        "income_cents": income,
        "expense_cents": expenses,
        "refund_cents": refunds,
        "internal_net_cents": internal,
        "movement_cents": total_movement,
        "review_count": review,
    }


def parsed_to_dict(parsed: ParsedStatement) -> dict[str, Any]:
    result = asdict(parsed)
    result["transactions"] = [asdict(item) for item in parsed.transactions]
    return result
