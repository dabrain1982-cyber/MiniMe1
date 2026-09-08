from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import report_store as store


def example():
    r = store.read_json(ROOT / "input" / "startbestand.json")
    now = datetime.now(timezone.utc)
    r["checked_at"] = now.isoformat()
    for item in r["listings"]:
        item["verified_at"] = now.isoformat()
    r.update(schema_version=2, mode="daily")
    # Synthetic evidence for validation tests only, never live search records.
    r["research"] = {
        "status": "complete",
        "actions": [
            {"id": "discover", "kind": "discovery", "source": "Test-Websuche",
             "url": "https://search.example.org/", "query": "TEST Mietwohnungen Östringen",
             "checked_at": now.isoformat(), "outcome": "ok", "result": "TEST Quellen entdeckt",
             "evidence_ref": "synthetic-test-discovery"},
            {"id": "search", "kind": "source_search", "source": "Test-Portal",
             "url": "https://portal.example.org/search", "query": "TEST Östringen Miete bis 1250",
             "checked_at": now.isoformat(), "outcome": "ok", "result": "TEST Angebotsliste geprüft",
             "evidence_ref": "synthetic-test-search"}],
        "source_decisions": [{"source": "Test-Portal", "url": "https://portal.example.org/",
                              "decision": "search", "reason": "TEST lokale Angebote"}],
        "review": {"findings": "TEST Quellen und Filter geprüft", "open_gaps": [],
                   "follow_up_action_ids": [], "stop_reason": "TEST Suchumfang abgearbeitet",
                   "criteria_proposal": "Keine Änderung vorgeschlagen"}}
    return r


class Reports(unittest.TestCase):
    def test_seed_valid(self):
        self.assertEqual(len(store.validate(example())["listings"]), 2)

    def test_missing_address_cannot_be_best(self):
        r = example()
        r["listings"][0]["group"] = "best"
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_unknown_floor_stays_clarification(self):
        r = example()
        r["listings"][0]["floor"] = None
        store.validate(r)

    def test_second_floor_excluded(self):
        r = example()
        r["listings"][0]["floor"] = 2
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_known_over_budget_excluded(self):
        r = example()
        r["listings"][0]["warm"] = 1251
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_mandatory_parking_over_budget_excluded(self):
        r = example()
        r["listings"][0]["mandatory_total"] = 1280
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_cold_budget_fallback(self):
        r = example()
        r["listings"][0]["warm"] = None
        r["listings"][0]["cold"] = 1001
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_inactive_original_rejected(self):
        r = example()
        r["listings"][0]["original_active"] = False
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_duplicate_url_ignores_tracking(self):
        r = example()
        r["listings"][1]["url"] = r["listings"][0]["url"] + "?utm_source=test"
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_duplicate_id_rejected(self):
        r = example()
        r["listings"][1]["id"] = r["listings"][0]["id"]
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_script_url_rejected(self):
        for url in ("javascript:alert(1)", "http://example.org", "https://localhost/a", "https://127.0.0.1/a", "https://user:secret@example.org/a"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                store.safe_url(url)

    def test_stale_verification_rejected(self):
        r = example()
        r["listings"][0]["verified_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_no_timezone_rejected(self):
        with self.assertRaises(ValueError):
            store.timestamp("2026-09-07T12:00:00")

    def test_future_rejected(self):
        r = example()
        r["checked_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_empty_report_valid_and_honest(self):
        r = example()
        r["mode"] = "daily"
        r["listings"] = []
        self.assertIn("0 passende", store.summary(store.validate(r)))

    def test_questions_required_for_clarification(self):
        r = example()
        r["listings"][0]["questions"] = []
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_four_new_rejected_but_held_extra_allowed(self):
        r = example()
        base = r["listings"][0]
        r["listings"] = [{**deepcopy(base), "id": f"test-{n}", "url": f"https://example.org/{n}", "status": "new"} for n in range(4)]
        with self.assertRaises(ValueError):
            store.validate(r)
        r["listings"][3]["status"] = "held"
        store.validate(r)

    def test_compact_exception_needs_evidence(self):
        r = example()
        a = r["listings"][0]
        a.update(group="best", address="Testadresse", floor=0, budget_verified=True,
                 location_verified=True, questions=[], area=56, rooms=1)
        with self.assertRaises(ValueError):
            store.validate(r)
        a.update(compact_exception=True, garage_confirmed=True, layout_confirmed=True, criteria_note="Test: Nutzerfreigabe und Grundrissbeleg")
        store.validate(r)

    def test_sort_groups_then_priority(self):
        r = {"listings": [{"group": "clarify", "priority": 100, "id": "a"},
                           {"group": "good", "priority": 99, "id": "b"},
                           {"group": "best", "priority": 50, "id": "c"}]}
        self.assertEqual([i["id"] for i in store.ordered(r)], ["c", "b", "a"])

    def test_publish_persists_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            r = example()
            store.publish(r, folder)
            store.publish(r, folder)
            self.assertEqual(store.latest(folder), r)
            self.assertEqual(len(list((Path(folder) / "reports").glob("*.json"))), 1)

    def test_bad_report_does_not_replace_good(self):
        with tempfile.TemporaryDirectory() as folder:
            good = example()
            store.publish(good, folder)
            bad = deepcopy(good)
            bad["listings"][0]["warm"] = 9000
            with self.assertRaises(ValueError):
                store.publish(bad, folder)
            self.assertEqual(store.latest(folder), good)

    def test_old_report_cannot_replace_latest(self):
        with tempfile.TemporaryDirectory() as folder:
            good = example()
            store.publish(good, folder)
            old = deepcopy(good)
            day = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            old["checked_at"] = day
            for item in old["listings"]:
                item["verified_at"] = day
            for action in old["research"]["actions"]:
                action["checked_at"] = day
            with self.assertRaises(ValueError):
                store.publish(old, folder)

    def test_nan_rejected(self):
        r = example()
        r["listings"][0]["cold"] = float("nan")
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_truthy_text_is_not_verification(self):
        r = example()
        r["listings"][0]["budget_verified"] = "false"
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_malformed_nested_records_rejected(self):
        for field in ("images", "costs"):
            r = example()
            r["listings"][0][field] = [None]
            with self.subTest(field=field), self.assertRaises(ValueError):
                store.validate(r)
        with self.assertRaises(ValueError):
            store.validate([])

    def test_archive_selection_runs(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        archives = sorted((ROOT / "data" / "reports").glob("*.json"), reverse=True)
        self.assertTrue(archives)
        app.selectbox(key="archive_selection").select(archives[0]).run()
        self.assertFalse(app.exception)

    def test_ui_runs(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Startbestand" in s.value or "Suchergebnis" in s.value for s in app.subheader))
        self.assertGreaterEqual(len(app.get("link_button")), 2)

    def test_daily_without_new_search_is_rejected(self):
        r = example()
        r.update(scope="Keine neue Suche ausgeführt", source_checks=[], listings=[])
        del r["research"]
        with self.assertRaisesRegex(ValueError, "Recherchestatus"):
            store.validate(r)

    def test_recheck_is_not_new_search(self):
        r = example()
        for action in r["research"]["actions"]:
            action["kind"] = "recheck"
        with self.assertRaisesRegex(ValueError, "Web-Entdeckung"):
            store.validate(r)

    def test_discovery_alone_is_not_portal_search(self):
        r = example()
        r["research"]["actions"] = r["research"]["actions"][:1]
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_each_selected_source_needs_search(self):
        r = example()
        r["research"]["source_decisions"].append({"source": "Anderes Portal",
            "url": "https://other.example.org/", "decision": "search", "reason": "TEST"})
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_complete_requires_evidence_and_review(self):
        for mutation in ("evidence", "time", "gap", "followup", "sources", "review"):
            r = example()
            research = r["research"]
            if mutation == "evidence":
                research["actions"][0]["evidence_ref"] = ""
            elif mutation == "time":
                research["actions"][0]["checked_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            elif mutation == "gap":
                research["review"]["open_gaps"] = ["Regionale Anbieter nicht gesucht"]
            elif mutation == "followup":
                research["review"]["follow_up_action_ids"] = ["not-executed"]
            elif mutation == "sources":
                r["source_checks"] = []
            else:
                del research["review"]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                store.validate(r)

    def test_blocked_search_not_zero_results(self):
        r = example()
        r["listings"] = []
        r["research"]["actions"][1].update(outcome="blocked", problem="TEST Zugriff gesperrt")
        with self.assertRaises(ValueError):
            store.validate(r)
        r["research"]["status"] = "incomplete"
        r["research"]["review"]["open_gaps"] = ["Quelle gesperrt, keine ausreichende Alternative"]
        store.validate(r)
        self.assertIn("Recherche unvollständig", store.summary(r))
        self.assertNotIn("0 Treffer", store.mail_subject(r))

    def test_not_performed_can_publish_as_failure_only(self):
        r = example()
        r.update(listings=[], source_checks=[])
        r["research"].update(status="not_performed", actions=[], source_decisions=[])
        r["research"]["review"].update(findings="TEST Kein Webwerkzeug verfügbar",
            stop_reason="TEST Recherche nicht begonnen")
        with tempfile.TemporaryDirectory() as folder:
            result = store.publish(r, folder)
            self.assertEqual(store.latest(folder), r)
        self.assertIn("Recherche nicht durchgeführt", result["summary"])
        self.assertNotIn("0 Treffer", result["mail_subject"])

    def test_started_search_cannot_claim_not_performed(self):
        r = example()
        r["research"]["status"] = "not_performed"
        with self.assertRaises(ValueError):
            store.validate(r)

    def test_initial_or_legacy_cannot_bypass_publication_gate(self):
        for mode in ("initial", "daily"):
            r = example()
            r.update(schema_version=1, mode=mode)
            del r["research"]
            store.validate(r, allow_legacy=True)
            with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
                store.publish(r, folder)

    def test_mail_count_excludes_clarifications_known_and_held(self):
        r = example()
        self.assertEqual(store.mail_subject(r), "Dein Immobilien-Agent: 0 Treffer")
        # Count behavior only; deliberately not an eligibility test.
        r["listings"][0].update(group="good", status="new")
        self.assertEqual(store.mail_subject(r), "Dein Immobilien-Agent: 1 Treffer")
        r["listings"][0]["status"] = "held"
        self.assertEqual(store.mail_subject(r), "Dein Immobilien-Agent: 0 Treffer")

    def test_failed_search_ui_does_not_show_zero_results(self):
        from streamlit.testing.v1 import AppTest
        for status in ("not_performed", "incomplete"):
            r = example()
            r.update(listings=[], source_checks=[])
            r["research"].update(status=status, actions=[], source_decisions=[])
            r["research"]["review"]["open_gaps"] = ["TEST Suche nicht abgeschlossen"]
            store.validate(r)
            with self.subTest(status=status), patch.object(store, "latest", return_value=r):
                app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
                self.assertFalse(app.exception)
                titles = " ".join(s.value for s in app.subheader)
                self.assertIn("Recherche", titles)
                self.assertNotIn("0 passende", titles)
                self.assertNotIn("Heute keine belegbaren", titles)

    def test_complete_zero_results_ui(self):
        from streamlit.testing.v1 import AppTest
        r = example()
        r["listings"] = []
        with patch.object(store, "latest", return_value=r):
            app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20).run()
            self.assertFalse(app.exception)
            self.assertTrue(any("0 passende" in s.value for s in app.subheader))


if __name__ == "__main__":
    unittest.main()
