"""Mark's local read-only apartment board; no contacts or messages are sent."""
from datetime import datetime
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from report_store import DATA, GROUPS, latest, ordered, read_json, research_status, summary, timestamp, validate

st.set_page_config(page_title="Mark Makler · Deine Wohnungssuche", page_icon=":material/home:", layout="wide")

LABELS = {"best": ("Beste Treffer", "green", "SEHR PASSEND"),
          "good": ("Weitere passende Wohnungen", "blue", "PASSEND"),
          "clarify": ("Das musst du klären", "orange", "KLÄRUNGSBEDARF")}


def euro(value):
    return f"{value:,.0f}".replace(",", ".") + " €"


def md(value):
    """Listing prose stays plain Markdown text, never HTML or active links."""
    import re
    return re.sub(r"([\\`*_{}\[\]()#+.!<>|~])", r"\\\1", str(value))


def photos(item):
    images = item["images"]
    if images:
        st.image(images[0]["url"], caption=images[0]["caption"], width="stretch")
        if len(images) > 1:
            thumbs = st.columns(min(len(images) - 1, 2))
            for slot, picture in zip(thumbs, images[1:3]):
                with slot:
                    st.image(picture["url"], caption=picture["caption"], width="stretch")
        st.caption(f"Anzeigenbilder · {md(item['provider'])}")
    else:
        with st.container(border=True, height=270, vertical_alignment="center", horizontal_alignment="center"):
            st.subheader("Bilder im Original", icon=":material/photo_library:")
            st.caption("Für diese Anzeige konnte kein Bild zuverlässig eingebunden werden.")
            st.link_button("Bilder beim Anbieter ansehen", item["url"], icon=":material/open_in_new:")


def card(item, historical=False):
    _, color, badge = LABELS[item["group"]]
    with st.container(border=True, key="listing_" + item["id"], gap="medium"):
        left, right = st.columns([1.05, 1], gap="large")
        with left:
            photos(item)
        with right:
            with st.container(horizontal=True):
                st.badge(badge, color=color)
                st.caption({"new": "Neu", "known": "Bereits bekannt", "held": "Gehalten"}[item["status"]])
            st.subheader(md(item["title"]))
            st.caption(md(item["place"]) + (" · " + md(item["address"]) if item["address"] else " · Adresse nicht veröffentlicht"))
            if item["warm"] is not None:
                st.subheader(euro(item["warm"]) + (" warm" if item["budget_verified"] else " warm laut Anzeige*"))
            else:
                st.subheader(euro(item["cold"]) + " kalt")
                st.caption("Warmmiete noch zu erfragen")
            if item.get("warm") is not None and item["warm"] > 1200:
                st.warning("Über deiner 1.200-€-Schmerzgrenze", icon=":material/payments:")
            if not item["budget_verified"]:
                st.caption("*Gesamtkosten noch nicht abschließend geklärt.")
            st.write(f"{item['area']:g} m²  ·  {item['rooms']:g} Zimmer  ·  {md(item['floor_label'])}")
            if item["tags"]:
                with st.container(horizontal=True):
                    for tag in item["tags"]:
                        st.badge(md(tag), color="gray")
            st.markdown("**" + ("Warum sie interessant bleibt" if item["group"] == "clarify" else "Warum sie hier steht") + "**")
            st.write(md(item["reason"]))
            if item["questions"]:
                st.warning("**Dein nächster Schritt**\n\n" + md(item["questions"][0]), icon=":material/help:")
            elif item["risks"]:
                st.caption(md(item["risks"][0]))
            st.link_button("Originalanzeige", item["url"], icon=":material/open_in_new:", width="stretch")
        with st.expander("Details, Lage und offene Fragen", icon=":material/expand_more:"):
            a, b = st.columns(2, gap="large")
            with a:
                st.markdown("**Kosten im Einzelnen**")
                st.write("Kaltmiete: " + (euro(item["cold"]) if item["cold"] is not None else "nicht angegeben"))
                for cost in item["costs"]:
                    st.write(md(cost["label"]) + ": " + md(cost["value"]))
                st.write(md(item["cost_notes"]))
                st.markdown("**Ausstattung und Verfügbarkeit**")
                st.write("Außenbereich: " + md(item["outside"]))
                st.write("Verfügbar: " + md(item["availability"]))
                st.write("Haustiere: " + md(item["pets"]))
                st.write("Veröffentlicht / aktualisiert: " + md(item.get("listing_date") or "nicht angegeben"))
            with b:
                st.markdown("**Lage für die Katzen**")
                st.write(md(item["location_notes"]))
                st.write("Arbeitsweg: " + md(item["route"]))
                for risk in item["risks"]:
                    st.write("• " + md(risk))
                if item["questions"]:
                    st.markdown("**Das solltest du klären**")
                    for question in item["questions"]:
                        st.write("• " + md(question))
            checked = timestamp(item["verified_at"]).strftime("%d.%m.%Y · %H:%M")
            st.caption(f"Original geöffnet: {checked} · {md(item['provider'])} · Keine Zusicherung der Verfügbarkeit oder Katzensicherheit.")
            st.caption("Bitte antworte hier im Chat mit Halten oder Verwerfen und nenne die Wohnung. Mark schreibt keine Anbieter an.")
            if historical:
                st.caption("Archivansicht: Die Angaben gelten für den damaligen Prüfzeitpunkt.")


@st.fragment(run_every=30)
def board():
    with st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center"):
        with st.container():
            st.title("Mark Makler", icon=":material/home:")
            st.caption("Deine Wohnungssuche")
        st.caption("Östringen & Umgebung · Persönliche Übersicht")
    try:
        report = latest()
    except (OSError, ValueError, KeyError, TypeError) as error:
        st.error("Der aktuelle Bericht ist beschädigt oder unvollständig. Es werden keine ungeprüften Daten angezeigt.")
        st.caption(str(error))
        return
    if report is None:
        st.subheader("Der erste Suchbericht steht noch aus.")
        st.caption("Hier erscheinen echte Wohnungen – zuerst die besten Treffer, dann weitere passende und zuletzt offene Klärfälle.")
        return
    st.subheader(summary(report))
    checked = timestamp(report["checked_at"])
    new_count = sum(i["status"] == "new" for i in report["listings"])
    held_count = sum(i["status"] == "held" for i in report["listings"])
    state = research_status(report)
    st.caption(f"Berichtsstand {checked:%d.%m.%Y · %H:%M}")
    if state in ("complete", "initial"):
        st.caption(f"{new_count} neu · {held_count} gehalten")
    elif report["listings"]:
        st.warning("Die folgenden Karten sind ein geprüfter Teilstand, kein vollständiges Tagesergebnis.")
    if checked.date() < datetime.now().astimezone().date():
        st.warning("Noch kein Bericht für heute. Du siehst den letzten geprüften Stand.", icon=":material/schedule:")
    if report["mode"] == "initial":
        st.caption(md(report["scope"]))
    rows = ordered(report)
    for group in GROUPS:
        entries = [i for i in rows if i["group"] == group]
        if not entries:
            continue
        label, color, _ = LABELS[group]
        st.markdown(f"### :{color}[{label}]")
        for item in entries:
            card(item)
    if not rows:
        with st.container(border=True):
            st.subheader("Im durchsuchten Umfang keine belegbaren Angebote." if state == "complete"
                         else "Kein abschließendes Suchergebnis vorhanden.")
            st.write(md(report["scope"]))
    with st.expander("Suchprotokoll & Änderungen", icon=":material/fact_check:"):
        st.write(md(report["scope"]))
        research = report.get("research")
        if research:
            st.caption("Dokumentierte Rechercheaktionen · keine unabhängige Vollständigkeitsprüfung")
            for decision in research["source_decisions"]:
                st.write(md(f"Quellenwahl: {decision['source']} · {decision['decision']} · {decision['reason']}"))
            kinds = {"discovery": "Web- und Quellenentdeckung", "source_search": "Quellensuche",
                     "follow_up": "Nachrecherche", "recheck": "Original-/Bestandsprüfung"}
            for action in research["actions"]:
                st.markdown(f"**{kinds[action['kind']]} · {md(action['source'])}**")
                st.write(md(action["query"]))
                st.markdown(f"[Geprüfte Seite]({action['url']}) — {md(action['result'])}")
                st.caption(md(f"{action['checked_at']} · {action['outcome']} · Beleg: {action['evidence_ref']}"))
                if action.get("problem"):
                    st.write("Zugriffsproblem: " + md(action["problem"]))
                if action.get("resolution"):
                    st.write("Umgang damit: " + md(action["resolution"]))
            review = research["review"]
            st.write("Maklerprüfung: " + md(review["findings"]))
            for gap in review["open_gaps"]:
                st.write("Offene Suchlücke: " + md(gap))
            st.write("Abschlussgrund: " + md(review["stop_reason"]))
            st.write("Kriterienvorschlag: " + md(review["criteria_proposal"]))
        st.caption("Quellen- und Originalübersicht (keine Zählung durchsuchter Portale)")
        for source in report["source_checks"]:
            st.markdown(f"[{md(source['name'])}]({source['url']}) — {md(source['result'])}")
        for update in report["updates"]:
            st.write("• " + md(update))
        st.write("Nächster Schwerpunkt: " + md(report["strategy"]))
    with st.expander("Frühere Berichte", icon=":material/history:"):
        files = sorted((DATA / "reports").glob("*.json"), reverse=True)
        if not files:
            st.caption("Noch keine archivierten Berichte.")
        else:
            selected = st.selectbox("Bericht auswählen", [None] + files,
                                    format_func=lambda x: "Archivdatum wählen" if x is None else x.stem[:17].replace("_", " · "),
                                    key="archive_selection")
            if selected is not None:
                try:
                    old = validate(read_json(selected), allow_legacy=True)
                    st.caption("Archiv – kein aktueller Verfügbarkeitsnachweis")
                    st.write(summary(old))
                    for item in ordered(old):
                        card({**item, "id": "archive_" + item["id"]}, historical=True)
                except (OSError, ValueError, KeyError, TypeError):
                    st.error("Dieser Archivbericht kann nicht geladen werden.")
    st.caption("Für die Katzen zählt die Lage. Offene Angaben bleiben offen. Keine Kontakt- oder Antwortautomatik.")


board()
