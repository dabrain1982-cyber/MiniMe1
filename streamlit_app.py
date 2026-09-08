from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from finance_core import (
    INTERNAL_CATEGORY,
    MAIN_CATEGORIES,
    REFUND_CATEGORY,
    REVIEW_CATEGORY,
    ParseError,
    PeriodParseError,
    aggregate_amounts,
    existing_statement,
    get_merchant_rules,
    import_statement,
    init_db,
    load_statements,
    load_transactions,
    parse_statement_pdf,
    save_transaction_corrections,
)


APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("FINANZBILANZ_DB_PATH", APP_DIR / "data" / "finanzbilanz.sqlite3"))
TEST_MODE = os.environ.get("FINANZBILANZ_TEST_MODE") == "1"
MONTH_NAMES = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
COLORS = {
    "blue": "#5271EE",
    "mint": "#39D98A",
    "coral": "#F06E67",
    "gold": "#E8B85C",
    "navy": "#14243B",
    "muted": "#8490A5",
}


st.set_page_config(
    page_title="Meine Finanzbilanz",
    page_icon=":material/account_balance_wallet:",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html(
    """
    <style>
    .stApp {
      background:
        radial-gradient(circle at 10% 4%, rgba(82,113,238,.09), transparent 27rem),
        radial-gradient(circle at 92% 28%, rgba(57,217,138,.08), transparent 25rem),
        #eef2f8;
    }
    [data-testid="stMainBlockContainer"] { max-width: 1450px; }
    [data-testid="stSidebar"] { background: #14243b; }
    [data-testid="stSidebar"] * { color: rgba(255,255,255,.88); }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
      background: rgba(255,255,255,.07); border-color: rgba(255,255,255,.22);
    }
    .stTabs [data-baseweb="tab-list"] {
      gap: .35rem; background: #edf1f6; border-radius: 14px; padding: 5px;
    }
    .stTabs [data-baseweb="tab"] { border-radius: 10px; font-weight: 700; }
    .stTabs [aria-selected="true"] { background: white; box-shadow: 0 4px 15px rgba(39,52,77,.08); }
    [data-testid="stMetric"] {
      background: white; border: 1px solid #dfe5ef; border-radius: 20px;
      padding: 1.05rem 1.15rem; box-shadow: 0 10px 28px rgba(43,55,80,.055);
    }
    [data-testid="stMetricValue"] { font-size: 1.55rem; white-space: nowrap; }
    [data-testid="stVerticalBlockBorderWrapper"] {
      background: rgba(255,255,255,.96); border-color: #dfe5ef; border-radius: 20px;
      box-shadow: 0 10px 28px rgba(43,55,80,.045);
    }
    .st-key-insight_card {
      color: white; border: 0;
      background: radial-gradient(circle at 100% 0%, rgba(57,217,138,.26), transparent 44%),
                  linear-gradient(145deg, #14243b, #213754);
      border-radius: 20px; padding: 1rem;
    }
    .st-key-insight_card * { color: rgba(255,255,255,.90) !important; }
    .st-key-insight_card [data-testid="stCaptionContainer"] * { color: rgba(255,255,255,.62) !important; }
    @media (max-width: 720px) {
      [data-testid="stMainBlockContainer"] { padding-inline: .8rem; }
      h1 { font-size: 1.8rem !important; }
    }
    </style>
    """
)

init_db(DB_PATH)


def euro(cents: int | float, *, force_sign: bool = False) -> str:
    value = int(round(cents)) / 100
    sign = "+" if value > 0 and force_sign else ""
    rendered = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if value < 0:
        sign = "−"
    return f"{sign}{rendered} €"


def percent_delta(current: int, comparison: int) -> str | None:
    if comparison == 0:
        return None
    change = (current - comparison) / abs(comparison) * 100
    sign = "+" if change > 0 else ""
    return f"{sign}{change:.1f} %".replace(".", ",")


def month_label(iso_date: str) -> str:
    parsed = datetime.fromisoformat(iso_date)
    return f"{MONTH_NAMES[parsed.month - 1]} {parsed.year}"


def transactions_frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["booking_date"] = pd.to_datetime(df["booking_date"])
    df["value_date"] = pd.to_datetime(df["value_date"])
    df["amount_eur"] = df["amount_cents"] / 100
    df["party"] = df["party"].fillna("")
    df.loc[df['booking_text'].str.contains('GIROCARD', case=False) | df['purpose'].str.contains('MONATLICHES ENTGELT GIROCARD', case=False), 'party'] = 'ING – Girocard-Gebühr'
    df["merchant"] = df["merchant"].replace('Nicht eindeutig', '')
    return df


def render_expense_ranking(expenses: pd.DataFrame) -> None:
    """Direct labels and proportional bars remain readable even in narrow cards."""
    if expenses.empty:
        st.caption('Keine Ausgaben vorhanden.')
        return
    frame = expenses.copy()
    frame['Anzeige'] = frame['main_category']
    frame.loc[frame['merchant'].eq('Amazon'), 'Anzeige'] = 'Amazon-Einkäufe'
    frame.loc[frame['merchant'].eq('Amazon Prime'), 'Anzeige'] = 'Amazon Prime'
    grouped = (-frame.groupby('Anzeige')['amount_cents'].sum()).sort_values(ascending=False)
    total = int(grouped.sum())
    for label, cents in grouped.items():
        share = f"{100 * cents / total:.1f}".replace('.', ',')
        st.markdown(f"**{label}** — {euro(int(cents))} · {share} %")
        st.progress(float(cents / grouped.iloc[0]))


def render_import_area() -> None:
    st.markdown("### :material/upload_file: Kontoauszüge")
    st.caption("PDFs werden nur lokal verarbeitet. Die Originaldatei wird nicht gespeichert.")
    uploads = st.file_uploader(
        "PDF-Kontoauszüge auswählen",
        type="pdf",
        accept_multiple_files=True,
        max_upload_size=30,
        key="statement_uploads",
    )
    if not uploads:
        return
    rules = get_merchant_rules(DB_PATH)
    for upload in uploads:
        data = upload.getvalue()
        file_hash = __import__("hashlib").sha256(data).hexdigest()
        duplicate = existing_statement(DB_PATH, file_hash)
        with st.expander(upload.name, expanded=not bool(duplicate), icon=":material/description:"):
            if duplicate:
                st.info(
                    f"Bereits am {duplicate['imported_at'][:10]} importiert – keine zweite Runde fürs selbe Geld.",
                    icon=":material/content_copy:",
                )
                continue
            parsed = None
            try:
                parsed = parse_statement_pdf(data, upload.name, rules)
            except PeriodParseError as exc:
                st.warning(str(exc), icon=":material/calendar_month:")
                st.caption("Bitte bestätige den Zeitraum direkt anhand des Kontoauszugs. Es wird nichts aus dem Dateinamen geraten.")
                date_cols = st.columns(2)
                with date_cols[0]:
                    manual_start = st.date_input(
                        "Beginn des Abrechnungszeitraums",
                        value=None,
                        format="DD.MM.YYYY",
                        key=f"manual_start_{file_hash}",
                    )
                with date_cols[1]:
                    manual_end = st.date_input(
                        "Ende des Abrechnungszeitraums",
                        value=None,
                        format="DD.MM.YYYY",
                        key=f"manual_end_{file_hash}",
                    )
                if manual_start and manual_end:
                    try:
                        parsed = parse_statement_pdf(
                            data,
                            upload.name,
                            rules,
                            period_override=(manual_start, manual_end),
                        )
                    except ParseError as manual_exc:
                        st.error(str(manual_exc), icon=":material/error:")
                        continue
                else:
                    continue
            except ParseError as exc:
                st.error(str(exc), icon=":material/error:")
                continue
            if parsed is None:
                continue
            meta = {
                "Geschütztes Konto": parsed.account_masked,
                "Zeitraum": f"{datetime.fromisoformat(parsed.period_start):%d.%m.%Y} – {datetime.fromisoformat(parsed.period_end):%d.%m.%Y}",
                "Anfangssaldo": euro(parsed.beginning_cents, force_sign=True),
                "Endsaldo": euro(parsed.ending_cents, force_sign=True),
                "Erkannte Buchungen": str(len(parsed.transactions)),
            }
            st.table(meta, border="horizontal", width="content")
            if parsed.confirmed:
                st.success("Cent-genau abgestimmt: Endsaldo = Anfangssaldo + Buchungssumme.", icon=":material/check_circle:")
            else:
                st.error(
                    f"Nicht abgestimmt. Differenz: {euro(parsed.reconciliation_diff_cents, force_sign=True)}. "
                    "Der Import bleibt gesperrt, bis die Differenz geklärt ist.",
                    icon=":material/price_check:",
                )
            review_count = sum(tx.main_category == REVIEW_CATEGORY for tx in parsed.transactions)
            st.caption(f"{review_count} Buchung(en) sind nach dem Import manuell zu prüfen.")
            if st.button(
                "Geprüften Auszug lokal importieren",
                key=f"import_{parsed.file_hash}",
                type="primary",
                icon=":material/save:",
                disabled=not parsed.confirmed,
            ):
                try:
                    result = import_statement(DB_PATH, parsed)
                except ParseError as exc:
                    st.error(str(exc), icon=":material/error:")
                else:
                    if result["duplicate"]:
                        st.info("Dieser Kontoauszug war bereits gespeichert.")
                    else:
                        st.toast(
                            f"{result['imported']} neue Buchungen gespeichert; "
                            f"{result['overlap_duplicates']} überlappende Dubletten übersprungen.",
                            icon=":material/check_circle:",
                        )
                        st.rerun()


def render_status(statements: list[dict], tx_rows: list[dict]) -> None:
    with st.sidebar:
        st.markdown("## :material/account_balance_wallet: Meine Finanzbilanz")
        if statements:
            latest = statements[-1]
            st.badge(
                "Aktuell abgestimmt" if latest["confirmed"] else "Prüfung nötig",
                color="green" if latest["confirmed"] else "orange",
                icon=":material/check:" if latest["confirmed"] else ":material/warning:",
            )
            month_word = "Monat" if len(statements) == 1 else "Monate"
            st.caption(f"{latest['account_masked']} · {len(statements)} {month_word} · {len(tx_rows)} Buchungen")
        else:
            st.badge("Bereit für den ersten Auszug", color="blue", icon=":material/hourglass_empty:")
        render_import_area()
        st.space("small")
        st.caption(f"Lokale Datenbank: {DB_PATH}")


def landscape(height=120, position=50):
    import base64
    asset = APP_DIR / "assets" / "abendruhe.png"
    if asset.exists():
        encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
        st.html(f'<img alt="Ruhiger See im warmen Abendlicht" src="data:image/png;base64,{encoded}" style="width:100%;height:{height}px;object-fit:cover;object-position:50% {position}%;border-radius:16px;display:block">')


def metric_row(items: list[tuple[str, str, str | None, str]], averages=None) -> None:
    groups = [items] if len(items) <= 4 else [items[:3], items[3:]]
    for group in groups:
        columns = st.columns(len(group))
        for column, (label, value, delta, color) in zip(columns, group):
            with column:
                if averages and label in averages:
                    from html import escape
                    decreasing = bool(delta and delta.startswith(("-", "−")))
                    delta_color = "#168451" if decreasing == (color == "inverse") else "#bd4545"
                    st.html(f'''<div style="position:relative;height:154px;padding:16px;background:white;border:1px solid #dfe5ef;border-radius:16px">
                        <div style="text-align:right;font-size:12px;color:#52627a" title="Durchschnitt über alle eingelesenen Monate">Ø / Monat: {escape(averages[label])}</div>
                        <div style="font-size:14px;margin-top:8px">{escape(label)}</div>
                        <div style="font-size:30px;font-weight:600">{escape(value)}</div>
                        <div style="font-size:14px;color:{delta_color}">{escape(delta or '')}</div></div>''')
                    continue
                st.metric(
                    label,
                    value,
                    delta=delta,
                    delta_color=color,
                    border=False,
                )


def monthly_summary(statements: list[dict], all_tx: list[dict]) -> pd.DataFrame:
    records = []
    for statement in statements:
        tx = [row for row in all_tx if row["statement_id"] == statement["id"]]
        amounts = aggregate_amounts(tx)
        records.append(
            {
                "statement_id": statement["id"],
                "Monat": month_label(statement["period_start"]),
                "Sortierung": statement["period_start"],
                "Einnahmen": amounts["income_cents"] / 100,
                "Ausgaben": amounts["expense_cents"] / 100,
                "Kontozuwachs": (statement["ending_cents"] - statement["beginning_cents"]) / 100,
                "Endkontostand": statement["ending_cents"] / 100,
                "Bestätigt": bool(statement["confirmed"]),
            }
        )
    return pd.DataFrame(records)


def overview_insights(summary: pd.DataFrame, tx_df: pd.DataFrame) -> list[str]:
    insights: list[str] = []
    expenses = tx_df[(tx_df["amount_cents"] < 0) & (tx_df["main_category"] != INTERNAL_CATEGORY)]
    if not expenses.empty:
        grouped = expenses.groupby("main_category")["amount_cents"].sum().abs().sort_values(ascending=False)
        share = grouped.iloc[0] / grouped.sum() * 100 if grouped.sum() else 0
        insights.append(f"Größter Ausgabenblock: {grouped.index[0]} mit {euro(int(grouped.iloc[0]))} ({share:.0f} %).")
    if len(summary) >= 2:
        current = int(round(summary.iloc[-1]["Ausgaben"] * 100))
        previous = int(round(summary.iloc[-2]["Ausgaben"] * 100))
        delta = current - previous
        direction = "mehr" if delta > 0 else "weniger"
        insights.append(f"Im jüngsten Monat fielen {euro(abs(delta))} {direction} Ausgaben an als im Vormonat.")
    unresolved = int((tx_df["main_category"] == REVIEW_CATEGORY).sum())
    if unresolved:
        insights.append(f"{unresolved} Buchung(en) sind noch ungeklärt; Auswertungen nach Kategorie bleiben dort vorläufig.")
    elif not tx_df.empty:
        insights.append("Alle gespeicherten Buchungen haben aktuell eine bestätigte oder automatisch nachvollziehbare Kategorie.")
    return insights[:3]


def render_overview(statements: list[dict], tx_rows: list[dict]) -> None:
    st.markdown("#### DEIN FINANZIELLES GESAMTBILD")
    st.title("Geld, aber übersichtlich.")
    if not statements:
        st.caption("Noch keine echten Monatswerte – und erfreulicherweise auch keine erfundenen.")
        st.info(
            "Lade links einen textbasierten PDF-Kontoauszug hoch. Erst nach Vorschau und Prüfung wird er lokal gespeichert.",
            icon=":material/upload_file:",
        )
        return
    summary = monthly_summary(statements, tx_rows)
    tx_df = transactions_frame(tx_rows)
    totals = aggregate_amounts(tx_rows)
    open_credits = sum(row["amount_cents"] for row in tx_rows if row["amount_cents"] > 0 and row["main_category"] == REVIEW_CATEGORY)
    if open_credits:
        st.info(f"Zusätzlich {euro(open_credits)} ungeklärte Gutschriften. Sie sind im Kontostand enthalten, aber noch nicht als Einnahmen oder Erstattungen eingeordnet.")
    total_growth = sum(s['ending_cents'] - s['beginning_cents'] for s in statements)
    unconfirmed = sum(not row["confirmed"] for row in statements)
    month_word = "eingelesener Monat" if len(statements) == 1 else "eingelesene Monate"
    subtitle = f"{summary.iloc[0]['Monat']} bis {summary.iloc[-1]['Monat']} · {len(statements)} {month_word}"
    st.caption(subtitle + (f" · {unconfirmed} davon nicht abgestimmt" if unconfirmed else " · cent-genau abgestimmt"))
    metric_row(
        [
            ("Zuwachs " + summary.iloc[-1]["Monat"], euro(int(round(summary.iloc[-1]["Kontozuwachs"] * 100)), force_sign=True), None, "normal"),
            ("Ø Zuwachs pro Monat", euro(int(round(summary["Kontozuwachs"].mean() * 100)), force_sign=True), None, "normal"),
            ("Kontozuwachs insgesamt", euro(total_growth, force_sign=True), None, "normal"),
            ("Aktueller Kontostand", euro(statements[-1]["ending_cents"], force_sign=True), None, "normal"),
        ]
    )

    from month_timeline import timeline_html
    amazon_values = [-sum(r['amount_cents'] for r in tx_rows if r['statement_id'] == item['id'] and r['amount_cents'] < 0 and r['merchant'] in {'Amazon', 'Amazon Prime'}) for item in statements]
    st.html(timeline_html(summary['Monat'].tolist(),
        [item['ending_cents'] - item['beginning_cents'] for item in statements],
        amazon_values, euro), unsafe_allow_javascript=True)
    with st.expander("Einnahmen, Ausgaben und Erstattungen ergänzend"):
        st.write(f"Einnahmen: {euro(totals['income_cents'])} · Ausgaben: {euro(totals['expense_cents'])} · Erstattungen einschließlich Kautionsrückzahlung: {euro(totals['refund_cents'])}")
    chart_col, category_col = st.columns([1.15, 0.85])
    with chart_col:
        with st.container(border=True):
            st.subheader("Entwicklung der Monatsendstände")
            line = (
                alt.Chart(summary)
                .mark_line(point=True, strokeWidth=4, color=COLORS["blue"])
                .encode(
                    x=alt.X("Monat:N", sort=summary["Monat"].tolist(), title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y("Endkontostand:Q", title="Euro", scale=alt.Scale(zero=False)),
                    tooltip=["Monat:N", alt.Tooltip("Endkontostand:Q", format=",.2f")],
                )
                .properties(height=260)
            )
            st.altair_chart(line, width="stretch")
        with st.container(border=True):
            st.subheader("Der ruhige Blick")
            landscape(150)
            for insight in overview_insights(summary, tx_df):
                st.write(insight)
    with category_col:
        with st.container(border=True):
            st.subheader("Wohin das Geld fließt")
            expense_df = tx_df[(tx_df["amount_cents"] < 0) & (tx_df["main_category"] != INTERNAL_CATEGORY)].copy()
            if expense_df.empty:
                st.caption("Noch keine auswertbaren Ausgaben.")
            else:
                render_expense_ranking(expense_df)

    with st.container(border=True):
        st.subheader("Relevante Händler")
        merchant_df = tx_df[(tx_df["amount_cents"] < 0) & tx_df["merchant"].ne("")]
        if merchant_df.empty:
            st.caption("Noch keine eindeutig erkannten Händler.")
        else:
            merchants = merchant_df.groupby("merchant", as_index=False).agg(
                Ausgaben=("amount_eur", lambda values: abs(values.sum())),
                Buchungen=("id", "count"),
                Durchschnitt=("amount_eur", lambda values: abs(values.mean())),
            ).sort_values("Ausgaben", ascending=False).head(12)
            st.dataframe(
                merchants,
                hide_index=True,
                column_config={
                    "merchant": st.column_config.TextColumn("Händler", pinned=True),
                    "Ausgaben": st.column_config.NumberColumn("Ausgaben", format="euro"),
                    "Buchungen": st.column_config.NumberColumn("Buchungen", format="%d"),
                    "Durchschnitt": st.column_config.NumberColumn("Ø Betrag", format="euro"),
                },
            )


def render_amazon(tx_rows: list[dict], statements: list[dict]) -> None:
    with st.container(border=True):
        st.subheader("Amazon-Ausgaben pro Monat" if len(statements) > 1 else "Amazon in diesem Monat")
        records = []
        for statement in statements:
            rows = [r for r in tx_rows if r['statement_id'] == statement['id'] and r['amount_cents'] < 0]
            shopping = -sum(r['amount_cents'] for r in rows if r['merchant'] == 'Amazon')
            prime = -sum(r['amount_cents'] for r in rows if r['merchant'] == 'Amazon Prime')
            records.append({'Monat': month_label(statement['period_start']), 'Amazon': (shopping + prime) / 100,
                            'Betrag': euro(shopping + prime)})
        if len(records) > 1:
            frame = pd.DataFrame(records)
            chart = alt.Chart(frame).mark_bar(color=COLORS['blue'], cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
                x=alt.X('Monat:N', sort=frame['Monat'].tolist(), title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Amazon:Q', title='Euro'), tooltip=['Monat:N', alt.Tooltip('Betrag:N', title='An Amazon gezahlt')]).properties(height=170)
            st.altair_chart(chart, width='stretch')
            st.caption(' · '.join(f"{r['Monat']}: {r['Betrag']}" for r in records))
        else:
            st.metric('An Amazon gezahlt', records[0]['Betrag'])
        st.caption('Alle Amazon-Abbuchungen einschließlich Prime im jeweiligen Buchungsmonat.')


def build_waterfall(statement: dict, tx: list[dict]) -> pd.DataFrame:
    amounts = aggregate_amounts(tx)
    expense_rows = [
        row for row in tx
        if row["amount_cents"] < 0 and row["main_category"] != INTERNAL_CATEGORY
    ]
    categories: dict[str, int] = {}
    for row in expense_rows:
        category = "Amazon-Einkäufe" if row["merchant"] == "Amazon" else "Amazon Prime" if row["merchant"] == "Amazon Prime" else row["main_category"]
        categories[category] = categories.get(category, 0) + (-int(row["amount_cents"]))
    ordered = sorted(categories.items(), key=lambda item: item[1], reverse=True)
    top = ordered[:4]
    other_expenses = sum(value for _, value in ordered[4:])
    steps: list[tuple[str, int, str]] = [("Anfangsstand", int(statement["beginning_cents"]), "Saldo")]
    if amounts["income_cents"]:
        steps.append(("Einnahmen", amounts["income_cents"], "Zugang"))
    for name, value in top:
        steps.append((name, -value, "Ausgabe"))
    if other_expenses:
        steps.append(("Weitere Ausgaben", -other_expenses, "Ausgabe"))
    ending = int(statement["ending_cents"])
    other = sum(int(row["amount_cents"]) for row in tx if row["main_category"] == INTERNAL_CATEGORY or (int(row["amount_cents"]) > 0 and row["main_category"] in {REFUND_CATEGORY, REVIEW_CATEGORY}))
    if other:
        steps.append(("Weitere Kontobewegungen", other, "Zugang" if other > 0 else "Ausgabe"))

    rows = []
    running = 0
    for index, (label, value, kind) in enumerate(steps):
        if index == 0:
            start, end = 0, value
            running = value
        else:
            start, end = running, running + value
            running = end
        rows.append({"Schritt": label, "Start": start / 100, "Ende": end / 100, "Betrag": value / 100, "Art": kind, "Reihenfolge": index})
    rows.append({"Schritt": "Endstand", "Start": 0, "Ende": ending / 100, "Betrag": ending / 100, "Art": "Saldo", "Reihenfolge": len(rows)})
    return pd.DataFrame(rows)


def render_month(statements: list[dict], tx_rows: list[dict]) -> None:
    st.markdown("#### MONAT IM DETAIL")
    if not statements:
        st.title("Noch kein Monat ausgewählt")
        st.caption("Nach dem ersten Import wird hier jeder Monat vollständig aufgeschlüsselt.")
        return
    labels = [month_label(row["period_start"]) for row in statements]
    selected_label = st.selectbox("Monat auswählen", labels, index=len(labels) - 1, key="selected_month", bind="query-params")
    index = labels.index(selected_label)
    statement = statements[index]
    month_rows = [row for row in tx_rows if row["statement_id"] == statement["id"]]
    month_df = transactions_frame(month_rows)
    amounts = aggregate_amounts(month_rows)
    growth = statement["ending_cents"] - statement["beginning_cents"]
    previous_rows = [] if index == 0 else [row for row in tx_rows if row["statement_id"] == statements[index - 1]["id"]]
    previous = aggregate_amounts(previous_rows) if previous_rows else None
    average_expenses = int(round(sum(monthly_summary(statements[:index], tx_rows)["Ausgaben"]) * 100 / index)) if index else 0

    st.title(selected_label)
    landscape(100, 45)
    status_text = "cent-genau abgestimmt" if statement["confirmed"] else f"nicht bestätigt · Differenz {euro(statement['reconciliation_diff_cents'], force_sign=True)}"
    st.caption(f"{len(month_rows)} gespeicherte Buchungen · {status_text}")
    metric_row(
        [
            ("Einnahmen", euro(amounts["income_cents"], force_sign=True), percent_delta(amounts["income_cents"], previous["income_cents"]) if previous else None, "normal"),
            ("Ausgaben", euro(-amounts["expense_cents"]), percent_delta(amounts["expense_cents"], previous["expense_cents"]) if previous else None, "inverse"),
            ("Kontozuwachs", euro(growth, force_sign=True), None, "normal"),
            ("Anfangsstand", euro(statement["beginning_cents"], force_sign=True), None, "normal"),
            ("Endstand", euro(statement["ending_cents"], force_sign=True), None, "normal"),
        ],
        averages={name: euro(int(round(monthly_summary(statements, tx_rows)[name].mean() * 100)))
                  for name in ("Einnahmen", "Ausgaben", "Kontozuwachs")},
    )
    st.caption(f"Ø / Monat bezieht sich auf alle {len(statements)} eingelesenen Monate, unabhängig vom ausgewählten Monat.")

    if not statement["confirmed"]:
        st.error(
            "Der Kontoverlauf ist nicht freigegeben. Prüfe fehlende Buchungen, Vorzeichen und mehrzeilige PDF-Einträge.",
            icon=":material/warning:",
        )
    comparison_parts = []
    if previous:
        diff = amounts["expense_cents"] - previous["expense_cents"]
        comparison_parts.append(f"Zum Vormonat: {euro(abs(diff))} {'mehr' if diff > 0 else 'weniger'} Ausgaben")
    if index:
        diff_avg = amounts["expense_cents"] - average_expenses
        comparison_parts.append(f"Zum bisherigen Monatsdurchschnitt: {euro(abs(diff_avg))} {'darüber' if diff_avg > 0 else 'darunter'}")
    if comparison_parts:
        st.caption(" · ".join(comparison_parts))

    with st.container(border=True):
        st.subheader("Vom Anfangs- zum Endstand")
        waterfall_df = build_waterfall(statement, month_rows)
        chart = (
            alt.Chart(waterfall_df)
            .mark_bar(cornerRadius=5)
            .encode(
                x=alt.X("Schritt:N", sort=waterfall_df["Schritt"].tolist(), title=None, axis=alt.Axis(labelAngle=-25)),
                y=alt.Y("Start:Q", title="Kontostand in Euro"),
                y2="Ende:Q",
                color=alt.Color(
                    "Art:N",
                    scale=alt.Scale(domain=["Saldo", "Zugang", "Ausgabe"], range=[COLORS["blue"], COLORS["mint"], COLORS["coral"]]),
                    legend=alt.Legend(orient="top"),
                ),
                tooltip=["Schritt:N", alt.Tooltip("Betrag:Q", format=",.2f"), alt.Tooltip("Ende:Q", format=",.2f")],
            )
            .properties(height=335)
        )
        st.altair_chart(chart, width="stretch")
        st.caption("Höchstens vier größte Ausgabenkategorien; Rest als „Weitere Ausgaben“. Weitere Kontobewegungen umfassen z. B. Erstattungen oder interne Umbuchungen.")

    render_amazon(month_rows, [statement])
    left, right = st.columns([1.3, 0.85])
    with left:
        with st.container(border=True):
            st.subheader("Buchungen filtern und Zuordnungen prüfen")
            categories = sorted(month_df["main_category"].dropna().unique().tolist())
            with st.container(horizontal=True):
                search = st.text_input("Suche", placeholder="Händler, Buchungstext oder Verwendungszweck", key=f"search_{statement['id']}")
                selected_categories = st.multiselect("Hauptkategorien", categories, key=f"categories_{statement['id']}")
            filtered = month_df.copy()
            if search:
                needle = search.casefold()
                mask = filtered[["merchant", "booking_text", "purpose"]].fillna("").astype(str).apply(
                    lambda column: column.str.casefold().str.contains(needle, regex=False)
                ).any(axis=1)
                filtered = filtered[mask]
            if selected_categories:
                filtered = filtered[filtered["main_category"].isin(selected_categories)]
            edit_df = filtered[[
                "id", "booking_date", "party", "amount_eur", "main_category", "subcategory",
                "merchant", "value_date", "booking_text", "purpose", "direction", "category_status",
            ]].copy()
            edited = st.data_editor(
                edit_df,
                key=f"editor_{statement['id']}",
                hide_index=True,
                disabled=["id", "booking_date", "value_date", "party", "booking_text", "purpose", "amount_eur", "direction", "category_status"],
                column_config={
                    "id": None,
                    "booking_date": st.column_config.DateColumn("Buchung", format="DD.MM.YYYY", pinned=True),
                    "value_date": st.column_config.DateColumn("Wertstellung", format="DD.MM.YYYY"),
                    "party": st.column_config.TextColumn("Empfänger / Auftraggeber", width="medium", pinned=True),
                    "merchant": None,
                    "booking_text": st.column_config.TextColumn("Buchungstext", width="large"),
                    "purpose": st.column_config.TextColumn("Verwendungszweck", width="large"),
                    "main_category": st.column_config.SelectboxColumn("Hauptkategorie", options=MAIN_CATEGORIES, required=True, width="medium"),
                    "subcategory": st.column_config.TextColumn("Unterkategorie", width="medium"),
                    "amount_eur": st.column_config.NumberColumn("Betrag", format="euro"),
                    "direction": st.column_config.TextColumn("Soll/Haben"),
                    "category_status": st.column_config.TextColumn("Status"),
                },
                height=430,
            )
            if st.button("Korrekturen speichern", key=f"save_{statement['id']}", icon=":material/save:", type="primary"):
                updated = save_transaction_corrections(DB_PATH, edited.to_dict("records"))
                st.toast(f"{updated} Zuordnung(en) gespeichert. Bestätigte Händler werden künftig wiedererkannt.", icon=":material/check_circle:")
                st.rerun()
    with right:
        with st.container(border=True):
            st.subheader("Ausgaben – größte zuerst")
            expense_df = month_df[(month_df["amount_cents"] < 0) & (month_df["main_category"] != INTERNAL_CATEGORY)].copy()
            if expense_df.empty:
                st.caption("Keine Ausgaben vorhanden.")
            else:
                render_expense_ranking(expense_df)
            unresolved = int((month_df["main_category"] == REVIEW_CATEGORY).sum())
            if unresolved:
                st.warning(f"{unresolved} ungeklärte Buchung(en)", icon=":material/help:")
            large = month_df.loc[month_df["amount_cents"].abs().idxmax()] if not month_df.empty else None
            if large is not None:
                st.caption(f"Größte Einzelbewegung: {euro(int(large['amount_cents']), force_sign=True)} am {large['booking_date']:%d.%m.%Y}.")

    with st.container(border=True):
        st.subheader("Händlerauswertung")
        merchant_df = month_df[(month_df["amount_cents"] < 0) & month_df["merchant"].ne("")]
        if merchant_df.empty:
            st.caption("Keine eindeutig erkannten Händler in diesem Monat.")
        else:
            report = merchant_df.groupby("merchant", as_index=False).agg(
                Gesamtausgaben=("amount_eur", lambda values: abs(values.sum())),
                Buchungen=("id", "count"),
                Durchschnitt=("amount_eur", lambda values: abs(values.mean())),
            ).sort_values("Gesamtausgaben", ascending=False)
            st.dataframe(
                report,
                hide_index=True,
                column_config={
                    "merchant": st.column_config.TextColumn("Händler", pinned=True),
                    "Gesamtausgaben": st.column_config.NumberColumn("Gesamtausgaben", format="euro"),
                    "Buchungen": st.column_config.NumberColumn("Buchungen", format="%d"),
                    "Durchschnitt": st.column_config.NumberColumn("Ø Betrag", format="euro"),
                },
            )


@st.fragment(run_every=10)
def render_improvement(statements: list[dict], tx_rows: list[dict]) -> None:
    st.markdown("#### QUALITÄTSPRÜFUNG")
    st.title("Verbesserungsvorschlag")
    landscape(120, 60)
    unconfirmed = sum(not row["confirmed"] for row in statements)
    unresolved = sum(row["main_category"] == REVIEW_CATEGORY for row in tx_rows)

    with st.container(border=True):
        st.subheader("1. Mein ehrlicher Blick")
        if not statements:
            st.write(
                "Die Oberfläche ist ruhig, responsiv aufgebaut und zeigt noch keine Fantasiezahlen. Das ist fachlich richtig. "
                "Eine belastbare Prüfung von Zahlenlänge, Diagrammdichte und dem echten PDF-Layout ist aber erst mit Deinem ersten Auszug möglich."
            )
        elif unconfirmed:
            st.write(
                f"Die Bilanz ist bedienbar, aber {unconfirmed} Monat(e) sind rechnerisch nicht freigegeben. "
                "Ich würde Dir diese Monate klar als vorläufig präsentieren – genau so tut es die App."
            )
        else:
            st.write(
                "Die gespeicherten Monate sind cent-genau abgestimmt. Kennzahlen, Monatsvergleich und Wasserfall verwenden dieselbe Buchungsbasis; "
                f"{unresolved} Zuordnung(en) bleiben sichtbar als „Zu prüfen“ markiert."
            )

    from proposal_store import status
    result = status(DB_PATH)
    proposal = result['proposal']
    if result['pending']:
        st.info("Neuer Datenstand: Die Monatsprüfung und der neue Vorschlag stehen noch aus. Sobald sie im Workstream fertig sind, erscheint der Vorschlag hier automatisch.")
    if proposal:
        with st.container(border=True):
            st.caption(('Vorheriger Vorschlag' if result['pending'] else 'Aktueller Vorschlag') + ' · ' + proposal['created_at'][:10])
            st.subheader(proposal['title'])
            st.write(proposal['review'])
            st.write(proposal['description'])
            st.markdown('**Dein Vorteil**')
            st.write(proposal['benefit'])
            st.markdown('**Möglicher Nachteil**')
            st.write(proposal['drawback'])
            st.caption('Nur vorgeschlagen, nicht umgesetzt. Wir besprechen Deine Entscheidung hier im GPT-Chat.')


statements = load_statements(DB_PATH)
all_transactions = load_transactions(DB_PATH)
if TEST_MODE:
    st.warning("GENERALPROBE · Separate Testbilanz. Deine echte Bilanz auf Port 8501 bleibt unverändert.")
    from monthly_workstream import check_month
    check = check_month(DB_PATH)
    if check['missing']:
        st.info(f"Monats-To-do: Kontoauszug {', '.join(check['missing'])} fehlt. Bitte links hochladen und nach Prüfung speichern.")
    else:
        st.success("Der fällige Monat ist vorhanden. Keine erneute Upload-Aufforderung nötig.")
render_status(statements, all_transactions)

tabs = st.tabs(
    [
        ":material/monitoring: Gesamtübersicht",
        ":material/calendar_month: Monatsansicht",
        ":material/lightbulb: Verbesserungsvorschlag",
    ]
)
with tabs[0]:
    render_overview(statements, all_transactions)
with tabs[1]:
    render_month(statements, all_transactions)
with tabs[2]:
    render_improvement(statements, all_transactions)

st.caption("Private lokale Auswertung · keine Anlage-, Kredit-, Rechts- oder Steuerberatung")
