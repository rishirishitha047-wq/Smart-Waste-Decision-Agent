"""Tests for EcoMind AI tools, PolicyClassifier and HackathonAgent."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def clear_issues():
    """Reset in-memory ISSUES list before each test."""
    import agent.tools as tools_mod
    tools_mod.ISSUES.clear()
    yield
    tools_mod.ISSUES.clear()


# ---------------------------------------------------------------------------
# get_bin_status
# ---------------------------------------------------------------------------

class TestGetBinStatus:
    def test_valid_id(self):
        from agent.tools import get_bin_status
        r = get_bin_status.func("BIN-001") if hasattr(get_bin_status, "func") else get_bin_status("BIN-001")
        assert r["bin_id"] == "BIN-001"
        assert "fill_level" in r
        assert r["data_source"] == "simulated"

    def test_case_insensitive(self):
        from agent.tools import get_bin_status
        fn = get_bin_status.func if hasattr(get_bin_status, "func") else get_bin_status
        r = fn("bin-001")
        assert r["bin_id"] == "BIN-001"

    def test_unknown_id(self):
        from agent.tools import get_bin_status
        fn = get_bin_status.func if hasattr(get_bin_status, "func") else get_bin_status
        r = fn("BIN-999")
        assert "error" in r
        assert "BIN-999" in r["error"]

    def test_empty_id(self):
        from agent.tools import get_bin_status
        fn = get_bin_status.func if hasattr(get_bin_status, "func") else get_bin_status
        r = fn("")
        assert "error" in r
        assert "required" in r["error"]

    def test_whitespace_id(self):
        from agent.tools import get_bin_status
        fn = get_bin_status.func if hasattr(get_bin_status, "func") else get_bin_status
        r = fn("   ")
        assert "error" in r


# ---------------------------------------------------------------------------
# assess_collection_priority
# ---------------------------------------------------------------------------

class TestAssessCollectionPriority:
    def _fn(self):
        from agent.tools import assess_collection_priority
        return assess_collection_priority.func if hasattr(assess_collection_priority, "func") else assess_collection_priority

    def test_returns_all_bins_when_no_filter(self):
        fn = self._fn()
        r = fn(None)
        assert "bins" in r
        assert len(r["bins"]) == 10

    def test_sorted_descending(self):
        fn = self._fn()
        r = fn(None)
        scores = [b["priority_score"] for b in r["bins"]]
        assert scores == sorted(scores, reverse=True)

    def test_overflow_flag(self):
        fn = self._fn()
        r = fn(None)
        for b in r["bins"]:
            if b["fill_level"] >= 90:
                assert b["overflow"] is True
            else:
                assert b["overflow"] is False

    def test_priority_formula(self):
        """BIN-001 (fill=95) should have a very high priority score."""
        fn = self._fn()
        r = fn(["BIN-001"])
        assert len(r["bins"]) == 1
        b = r["bins"][0]
        # fill_level * 0.7 = 66.5 minimum; capped_hours contribution 0-30
        assert b["priority_score"] >= 66.5

    def test_filter_by_ids(self):
        fn = self._fn()
        r = fn(["BIN-001", "BIN-002"])
        assert len(r["bins"]) == 2
        ids = {b["bin_id"] for b in r["bins"]}
        assert ids == {"BIN-001", "BIN-002"}


# ---------------------------------------------------------------------------
# create_collection_plan
# ---------------------------------------------------------------------------

class TestCreateCollectionPlan:
    def _fn(self):
        from agent.tools import create_collection_plan
        return create_collection_plan.func if hasattr(create_collection_plan, "func") else create_collection_plan

    def test_default_capacity(self):
        fn = self._fn()
        r = fn(None)
        assert r["recommendation"] is True
        assert len(r["plan"]) <= 5
        assert "No real dispatch" in r["note"]

    def test_custom_capacity(self):
        fn = self._fn()
        r = fn(3)
        assert len(r["plan"]) <= 3

    def test_capacity_too_small(self):
        fn = self._fn()
        r = fn(0)
        assert "error" in r

    def test_capacity_negative(self):
        fn = self._fn()
        r = fn(-1)
        assert "error" in r

    def test_plan_has_ranks(self):
        fn = self._fn()
        r = fn(3)
        ranks = [p["rank"] for p in r["plan"]]
        assert ranks == list(range(1, len(ranks)+1))

    def test_recommendation_label(self):
        fn = self._fn()
        r = fn(None)
        assert r["recommendation"] is True
        assert r["data_source"] == "simulated"


# ---------------------------------------------------------------------------
# report_bin_issue
# ---------------------------------------------------------------------------

class TestReportBinIssue:
    def _fn(self):
        from agent.tools import report_bin_issue
        return report_bin_issue.func if hasattr(report_bin_issue, "func") else report_bin_issue

    def test_valid_report(self):
        fn = self._fn()
        r = fn("BIN-007", "Bin lid is broken and cannot be closed.")
        assert "report_id" in r
        assert r["report_id"].startswith("RPT-BIN-007-")
        assert r["status"] == "open"
        assert r["duplicate"] is False

    def test_unknown_bin(self):
        fn = self._fn()
        r = fn("BIN-999", "Some issue")
        assert "error" in r

    def test_empty_bin_id(self):
        fn = self._fn()
        r = fn("", "Some issue")
        assert "error" in r

    def test_empty_description(self):
        fn = self._fn()
        r = fn("BIN-007", "")
        assert "error" in r

    def test_description_too_long(self):
        fn = self._fn()
        r = fn("BIN-007", "x" * 501)
        assert "error" in r

    def test_description_exactly_500(self):
        fn = self._fn()
        r = fn("BIN-007", "x" * 500)
        assert "report_id" in r

    def test_duplicate_open_issue(self):
        fn = self._fn()
        desc = "Bin lid is broken"
        r1 = fn("BIN-007", desc)
        r2 = fn("BIN-007", desc)
        assert r1["report_id"] == r2["report_id"]
        assert r2["duplicate"] is True

    def test_duplicate_case_insensitive(self):
        fn = self._fn()
        r1 = fn("BIN-007", "Bin lid is broken")
        r2 = fn("BIN-007", "bin lid is broken")
        assert r1["report_id"] == r2["report_id"]


# ---------------------------------------------------------------------------
# PolicyClassifier
# ---------------------------------------------------------------------------

class TestPolicyClassifier:
    def _make_decider(self, category, confidence):
        from decider_kit.client import Decision
        mock_decision = MagicMock(spec=Decision)
        mock_decision.label = category
        mock_decision.probabilities = {
            "urgent_overflow": 0.0,
            "routine_collection": 0.0,
            "bin_issue": 0.0,
            "general_information": 0.0,
        }
        mock_decision.probabilities[category] = confidence
        mock_decision.confidence = confidence
        mock_decision.unsure = lambda threshold=0.7: confidence < threshold
        d = MagicMock()
        d.ask.return_value = {"category": mock_decision}
        d.last_latency_ms = 42.0
        return d

    def test_urgent_overflow(self):
        from agent.decision import PolicyClassifier
        pc = PolicyClassifier(self._make_decider("urgent_overflow", 0.91))
        r = pc.classify("The bin is overflowing!")
        assert r["category"] == "urgent_overflow"
        assert r["low_confidence"] is False

    def test_routine_collection(self):
        from agent.decision import PolicyClassifier
        pc = PolicyClassifier(self._make_decider("routine_collection", 0.85))
        r = pc.classify("Plan collection route for this week.")
        assert r["category"] == "routine_collection"
        assert r["low_confidence"] is False

    def test_bin_issue(self):
        from agent.decision import PolicyClassifier
        pc = PolicyClassifier(self._make_decider("bin_issue", 0.88))
        r = pc.classify("The bin lid is broken.")
        assert r["category"] == "bin_issue"
        assert r["low_confidence"] is False

    def test_general_information(self):
        from agent.decision import PolicyClassifier
        pc = PolicyClassifier(self._make_decider("general_information", 0.92))
        r = pc.classify("How often should bins be collected?")
        assert r["category"] == "general_information"
        assert r["low_confidence"] is False

    def test_low_confidence(self):
        from agent.decision import PolicyClassifier
        pc = PolicyClassifier(self._make_decider("urgent_overflow", 0.55))
        r = pc.classify("Something about a bin.")
        assert r["low_confidence"] is True

    def test_decision_record_appended(self):
        from agent.decision import PolicyClassifier
        pc = PolicyClassifier(self._make_decider("bin_issue", 0.80))
        pc.classify("Report a damaged bin.")
        assert len(pc.log) == 1
        rec = pc.log[0]
        assert rec["pattern"] == "#policy"
        assert rec["category"] == "bin_issue"
        assert "confidence" in rec
        assert "decider_ms" in rec

    def test_decider_error_fallback(self):
        from agent.decision import PolicyClassifier
        from decider_kit.client import DeciderError
        d = MagicMock()
        d.ask.side_effect = DeciderError("Connection refused")
        pc = PolicyClassifier(d)
        r = pc.classify("test message")
        assert r["low_confidence"] is True
        assert r["fallback"] if "fallback" in r else pc.log[0]["fallback"]
        assert r["error"] is not None


# ---------------------------------------------------------------------------
# HackathonAgent.chat()
# ---------------------------------------------------------------------------

class TestHackathonAgent:
    def _make_agent(self, category="routine_collection", confidence=0.85):
        from agent.decision import PolicyClassifier
        from decider_kit.client import Decision

        mock_decision = MagicMock(spec=Decision)
        mock_decision.label = category
        mock_decision.probabilities = {k: 0.0 for k in ["urgent_overflow","routine_collection","bin_issue","general_information"]}
        mock_decision.probabilities[category] = confidence
        mock_decision.confidence = confidence
        mock_decision.unsure = lambda threshold=0.7: confidence < threshold

        mock_decider = MagicMock()
        mock_decider.ask.return_value = {"category": mock_decision}
        mock_decider.last_latency_ms = 50.0

        from agent.agent import HackathonAgent
        agent = HackathonAgent.__new__(HackathonAgent)
        agent.decider = mock_decider
        agent.eager = False
        agent.model_id = "test-model"
        agent.classifier = PolicyClassifier(mock_decider)
        agent.sessions = {}
        return agent

    def test_chat_return_shape(self):
        a = self._make_agent()
        with patch("agent.agent.agent_model"), patch("strands.Agent") as MockAgent:
            MockAgent.return_value.return_value = MagicMock(__str__=lambda s: "Here is the collection plan.")
            result = a.chat("Plan a collection route.", "s1")
        assert "reply" in result
        assert "decisions" in result
        assert "model_id" in result
        assert "latency_ms" in result
        assert "agent" in result
        assert "eager" in result

    def test_decisions_list_has_one_record(self):
        a = self._make_agent()
        with patch("agent.agent.agent_model"), patch("strands.Agent") as MockAgent:
            MockAgent.return_value.return_value = MagicMock(__str__=lambda s: "Reply text.")
            result = a.chat("Plan a route.", "s2")
        assert len(result["decisions"]) == 1
        rec = result["decisions"][0]
        assert rec["pattern"] == "#policy"

    def test_low_confidence_short_circuits(self):
        a = self._make_agent(confidence=0.45)
        with patch("agent.agent.agent_model") as mock_model:
            result = a.chat("bin", "s3")
        # Should NOT call the LLM
        mock_model.assert_not_called()
        assert result["decisions"][0]["verdict"] == "low_confidence"
        assert "clarif" in result["reply"].lower() or "detail" in result["reply"].lower()

    def test_llm_error_returns_graceful_reply(self):
        a = self._make_agent()
        with patch("agent.agent.Agent") as MockAgent, patch("agent.agent.agent_model"):
            MockAgent.return_value.side_effect = Exception("Bedrock unavailable")
            result = a.chat("Plan a collection.", "s4_erruniq")
        assert "unavailable" in result["reply"].lower() or "try again" in result["reply"].lower()

    def test_agent_name(self):
        from agent.agent import NAME
        assert "EcoMind" in NAME
