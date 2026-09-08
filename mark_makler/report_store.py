"""Validated, atomic report handoff. No network calls, mail or finance imports."""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
GROUPS = ("best", "good", "clarify")
MAX_BYTES = 2_000_000


def timestamp(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("Zeitangaben benötigen eine Zeitzone.")
    return dt


def safe_url(value):
    if not isinstance(value, str):
        raise ValueError("Eine öffentliche HTTPS-URL ist erforderlich.")
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.port not in (None, 443) or any(c.isspace() for c in value)):
        raise ValueError("Nur öffentliche HTTPS-URLs ohne Zugangsdaten sind erlaubt.")
    import ipaddress
    try:
        address = ipaddress.ip_address(parts.hostname)
    except ValueError:
        if "." not in parts.hostname or parts.hostname.endswith((".local", ".localhost")):
            raise ValueError("Lokale Adressen sind nicht erlaubt.")
    else:
        if not address.is_global:
            raise ValueError("Interne Adressen sind nicht erlaubt.")
    return value


def canonical_url(value):
    p = urlsplit(safe_url(value))
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", ""))


def text(value, label, optional=False):
    if optional and value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > 6000:
        raise ValueError(f"{label}: gültigen Text angeben.")


def number(value, label, optional=False):
    if optional and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label}: gültige nichtnegative Zahl angeben.")


def validate_research(r, checked):
    """Check declared search evidence, not network execution or market completeness."""
    research = r.get("research")
    if not isinstance(research, dict) or research.get("status") not in ("complete", "incomplete", "not_performed"):
        raise ValueError("Expliziten Recherchestatus und Suchprotokoll angeben.")
    actions = research.get("actions")
    decisions = research.get("source_decisions")
    review = research.get("review")
    if not isinstance(actions, list) or not isinstance(decisions, list) or not isinstance(review, dict):
        raise ValueError("Suchaktionen, Quellenentscheidung und Maklerprüfung fehlen.")
    by_id = {}
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("Ungültige Suchaktion.")
        for field in ("id", "source", "query", "result", "evidence_ref"):
            text(action.get(field), field)
        if action["id"] in by_id:
            raise ValueError("Suchaktions-IDs müssen eindeutig sein.")
        safe_url(action.get("url"))
        when = timestamp(action["checked_at"])
        if when > checked or when.astimezone(checked.tzinfo).date() != checked.date():
            raise ValueError("Suchaktionen müssen zum aktuellen Berichtslauf gehören.")
        if action.get("kind") not in ("discovery", "source_search", "follow_up", "recheck"):
            raise ValueError("Unbekannte Suchaktionsart.")
        if action.get("outcome") not in ("ok", "blocked", "error"):
            raise ValueError("Sucherfolg oder Zugriffsproblem ausdrücklich angeben.")
        if action["outcome"] != "ok":
            text(action.get("problem"), "Zugriffsproblem")
        by_id[action["id"]] = action
    searched_sources = set()
    for decision in decisions:
        if not isinstance(decision, dict):
            raise ValueError("Ungültige Quellenentscheidung.")
        for field in ("source", "reason"):
            text(decision.get(field), field)
        safe_url(decision.get("url"))
        if decision.get("decision") not in ("search", "skip"):
            raise ValueError("Quellenauswahl begründen: search oder skip.")
        if decision["decision"] == "search":
            searched_sources.add(urlsplit(decision["url"]).hostname.removeprefix("www."))
    for field in ("findings", "stop_reason", "criteria_proposal"):
        text(review.get(field), field)
    gaps = review.get("open_gaps")
    followups = review.get("follow_up_action_ids")
    if not isinstance(gaps, list) or not isinstance(followups, list):
        raise ValueError("Offene Suchlücken und Nachrecherchen dokumentieren.")
    for gap in gaps:
        text(gap, "Suchlücke")
    for ident in followups:
        if not isinstance(ident, str) or ident not in by_id or by_id[ident]["kind"] != "follow_up":
            raise ValueError("Nachrecherche muss auf eine protokollierte Suchaktion verweisen.")
    status = research["status"]
    searches = [a for a in actions if a["kind"] != "recheck"]
    if status == "not_performed" and searches:
        raise ValueError("Bei versuchter Neusuche ist der Status unvollständig statt nicht durchgeführt.")
    if status == "incomplete" and not gaps:
        raise ValueError("Unvollständige Recherche benötigt eine konkrete offene Suchlücke.")
    if status == "complete":
        ok = [a for a in searches if a["outcome"] == "ok"]
        searched = {urlsplit(a["url"]).hostname.removeprefix("www.") for a in ok
                    if a["kind"] in ("source_search", "follow_up")}
        if not any(a["kind"] == "discovery" for a in ok) or not searched_sources or not searched_sources <= searched:
            raise ValueError("Abschluss erfordert aktuelle Web-Entdeckung und Suche in allen ausgewählten Quellen.")
        if not r["source_checks"] or gaps:
            raise ValueError("Ohne Quellenprotokoll oder mit offenen Suchlücken kein abgeschlossener Suchlauf.")
        for action in actions:
            if action["outcome"] != "ok":
                text(action.get("resolution"), "Ersatzprüfung oder begründete Begrenzung nach Zugriffsproblem")


def validate(report, *, allow_legacy=False):
    if not isinstance(report, dict):
        raise ValueError("Ein Bericht muss ein JSON-Objekt sein.")
    r = deepcopy(report)
    if r.get("schema_version") not in (1, 2) or r.get("mode") not in ("initial", "daily"):
        raise ValueError("Unbekanntes Berichtsformat.")
    if r["schema_version"] == 1 and r["mode"] == "daily" and not allow_legacy:
        raise ValueError("Neue Tagesberichte benötigen Schema 2 mit Rechercheprotokoll.")
    if r["schema_version"] == 2 and r["mode"] != "daily":
        raise ValueError("Neue Berichte sind Tagesläufe, kein neuer Startbestand.")
    checked = timestamp(r["checked_at"])
    if checked > datetime.now().astimezone():
        raise ValueError("Berichtszeit darf nicht in der Zukunft liegen.")
    text(r.get("scope"), "Suchumfang")
    text(r.get("strategy"), "Strategie")
    for field in ("source_checks", "updates", "listings"):
        if not isinstance(r.get(field), list):
            raise ValueError(f"{field} muss eine Liste sein.")
    for source in r["source_checks"]:
        if not isinstance(source, dict):
            raise ValueError("Ungültiger Quelleneintrag.")
        text(source.get("name"), "Quellenname")
        text(source.get("result"), "Quellenprüfung")
        safe_url(source.get("url"))
    for update in r["updates"]:
        text(update, "Änderung")
    if r["schema_version"] == 2:
        validate_research(r, checked)
    ids, urls = set(), set()
    new_count = 0
    for item in r["listings"]:
        if not isinstance(item, dict):
            raise ValueError("Ungültiger Wohnungseintrag.")
        for field in ("budget_verified", "location_verified", "route_plausible", "original_active"):
            if not isinstance(item.get(field), bool):
                raise ValueError(f"{field}: ausdrücklich true oder false angeben.")
        ident = item.get("id", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", ident) or ident in ids:
            raise ValueError("Wohnungs-IDs müssen eindeutig und stabil sein.")
        ids.add(ident)
        url = canonical_url(item.get("url"))
        if url in urls:
            raise ValueError("Doppelte Originalanzeige.")
        urls.add(url)
        for field in ("title", "place", "floor_label", "availability", "reason", "location_notes", "route", "pets", "outside", "cost_notes", "provider"):
            text(item.get(field), field)
        text(item.get("address"), "Adresse", optional=True)
        if item.get("group") not in GROUPS or item.get("status") not in ("new", "known", "held"):
            raise ValueError("Unbekannte Gruppe oder Verlaufsstatus.")
        new_count += item["status"] == "new"
        number(item.get("priority"), "Priorität")
        if item["priority"] > 100:
            raise ValueError("Priorität höchstens 100.")
        for field in ("area", "rooms"):
            number(item.get(field), field)
            if item[field] <= 0:
                raise ValueError("Fläche und Zimmer müssen positiv sein.")
        floor = item.get("floor")
        if floor is not None and (isinstance(floor, bool) or not isinstance(floor, (int, float)) or not math.isfinite(floor) or floor > 1 or floor < -2):
            raise ValueError("Nicht zulässige Etage.")
        for field in ("cold", "warm", "mandatory_total"):
            number(item.get(field), field, optional=True)
        if item.get("warm") is not None and item["warm"] > 1250:
            raise ValueError("Bekannte Warmmiete über 1.250 Euro.")
        if item.get("mandatory_total") is not None and item["mandatory_total"] > 1250:
            raise ValueError("Bekannte Pflichtkosten überschreiten das Gesamtbudget.")
        if item.get("warm") is None and (item.get("cold") is None or item["cold"] > 1000):
            raise ValueError("Ohne Warmmiete muss eine Kaltmiete bis 1.000 Euro bekannt sein.")
        if item.get("original_active") is not True:
            raise ValueError("Keine aktive Originalanzeige bestätigt.")
        verification = timestamp(item["verified_at"])
        if verification > checked or verification.date() != checked.date():
            raise ValueError("Originalanzeige muss am Berichtstag erneut geprüft werden.")
        if item.get("route_plausible") is not True:
            raise ValueError("Fahrstrecke nicht plausibel im Suchgebiet.")
        for field in ("questions", "risks", "tags", "images", "costs"):
            if not isinstance(item.get(field), list):
                raise ValueError(f"{field} muss eine Liste sein.")
        for field in ("questions", "risks", "tags"):
            for value in item[field]:
                text(value, field)
        for cost in item["costs"]:
            if not isinstance(cost, dict):
                raise ValueError("Ungültiger Kosteneintrag.")
            text(cost.get("label"), "Kostenart")
            text(cost.get("value"), "Kostenangabe")
        if len(item["images"]) > 8:
            raise ValueError("Höchstens acht Bilder pro Wohnung.")
        for image in item["images"]:
            if not isinstance(image, dict):
                raise ValueError("Ungültiger Bildeintrag.")
            safe_url(image.get("url"))
            safe_url(image.get("source"))
            text(image.get("caption"), "Bildbeschreibung")
        if item["group"] != "clarify":
            if (not item.get("address") or floor is None or not item.get("budget_verified")
                    or item.get("location_verified") is not True or item["questions"]):
                raise ValueError("Wesentliche offene Punkte gehören in die Klärgruppe.")
            if item["rooms"] < 2 or item["area"] < 60:
                if not (item.get("compact_exception") is True and item.get("garage_confirmed") is True and item.get("layout_confirmed") is True):
                    raise ValueError("Kompakte Ausnahme: Grundriss und Garage müssen belegt sein.")
                text(item.get("criteria_note"), "Begründung der kompakten Ausnahme")
        elif not item["questions"]:
            raise ValueError("Klärfälle benötigen konkrete Fragen.")
    if new_count > 3:
        raise ValueError("Höchstens drei neue Wohnungen; gehaltene und bekannte getrennt zählen.")
    return r


def ordered(report):
    return sorted(report["listings"], key=lambda x: (GROUPS.index(x["group"]), -x["priority"], x["id"]))


def summary(report):
    state = research_status(report)
    if state == "not_performed":
        return "Recherche nicht durchgeführt – keine Aussage über neue Angebote."
    if state == "incomplete":
        return "Recherche unvollständig – kein abschließendes Suchergebnis."
    if state == "legacy":
        return "Früherer Bericht – Neusuche nicht nach aktuellem Standard dokumentiert."
    rows = report["listings"]
    good = sum(i["group"] != "clarify" for i in rows)
    clarify = len(rows) - good
    prefix = "Startbestand" if report["mode"] == "initial" else "Suchergebnis"
    return f"{prefix}: {good} passende Wohnungen und {clarify} Angebote mit Klärungsbedarf."


def research_status(report):
    if report.get("mode") == "initial":
        return "initial"
    return report.get("research", {}).get("status", "legacy")


def mail_subject(report):
    state = research_status(report)
    if state != "complete":
        return "Dein Immobilien-Agent: " + {
            "not_performed": "Recherche nicht durchgeführt",
            "incomplete": "Recherche unvollständig",
            "initial": "Bestandsprüfung",
            "legacy": "Recherche nicht nachgewiesen",
        }[state]
    count = sum(i["status"] == "new" and i["group"] != "clarify" for i in report["listings"])
    return f"Dein Immobilien-Agent: {count} Treffer"


def read_json(path):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Berichtsdatei ist zu groß.")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def latest(data_dir=DATA):
    path = Path(data_dir) / "latest.json"
    return validate(read_json(path), allow_legacy=True) if path.exists() else None


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".report-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def publish(report, data_dir=DATA):
    r = validate(report)
    if r["schema_version"] != 2 or r["mode"] != "daily":
        raise ValueError("Veröffentlichen erfordert Schema 2 mit Rechercheprotokoll; Altbestand nur lesen.")
    data_dir = Path(data_dir)
    previous = latest(data_dir)
    if previous and timestamp(r["checked_at"]) < timestamp(previous["checked_at"]):
        raise ValueError("Ein älterer Bericht darf den aktuellen nicht ersetzen.")
    fingerprint = hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    stamp = timestamp(r["checked_at"]).strftime("%Y-%m-%d_%H%M%S")
    archive = data_dir / "reports" / f"{stamp}_{fingerprint[:12]}.json"
    if not archive.exists():
        atomic_json(archive, r)
    atomic_json(data_dir / "latest.json", r)
    return {"published": True, "summary": summary(r), "mail_subject": mail_subject(r), "archive": str(archive)}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("action", choices=("publish", "validate", "status"))
    cli.add_argument("source", nargs="?", type=Path)
    args = cli.parse_args()
    if args.action == "status":
        r = latest()
        print(json.dumps({"report": r, "summary": summary(r) if r else None,
                          "mail_subject": mail_subject(r) if r else None}, ensure_ascii=False))
    elif args.source is None:
        cli.error("Eine Quelldatei ist erforderlich.")
    else:
        r = validate(read_json(args.source))
        print(json.dumps(publish(r) if args.action == "publish" else {"valid": True, "summary": summary(r)}, ensure_ascii=False))
