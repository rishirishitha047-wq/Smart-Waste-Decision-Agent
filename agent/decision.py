"""REUSABLE DECISION PATTERN: policy classification  (#policy)

What it does
    Classifies every incoming waste-management request into one of four categories
    before the Strands Agent runs. The classified category is injected into the agent
    system prompt so the LLM selects the appropriate tools without hard-coded routing.

Typed questions and options
    `category` (choice): urgent_overflow | routine_collection | bin_issue | general_information

Wiring
    PolicyClassifier is called as a pre-processing step in HackathonAgent.chat():

        result = self.classifier.classify(message)
        if result["low_confidence"]:
            return clarification_reply(...)
        system_prompt = BASE + CATEGORY_PROMPT_ADDITION[result["category"]]
        agent = Agent(system_prompt=system_prompt, ...)
        agent(message)

    This is NOT an InterventionHandler. It runs before the Strands Agent is invoked,
    so the classification shapes the system prompt for that turn.

How to reuse it
    Copy this file. Replace CATEGORY_QUESTION criteria with your own policy taxonomy.
    Adjust confidence_threshold in PolicyClassifier.__init__ for your domain.
"""

from __future__ import annotations

import time
from typing import Any

from decider_kit import Decider
from decider_kit.client import DeciderError

PATTERN_TAG = "#policy"

# ---------------------------------------------------------------------------
# Typed question — the single Decider call per chat() turn
# ---------------------------------------------------------------------------

CATEGORY_QUESTION = Decider.choice(
    "Which type of waste-management request is this?",
    {
        "urgent_overflow": (
            "A bin is overflowing, nearly full, causing a sanitation or health concern, "
            "or needs emergency collection."
        ),
        "routine_collection": (
            "A request to plan, schedule or check routine waste collection "
            "with no overflow or sanitation concern."
        ),
        "bin_issue": (
            "A bin is damaged, inaccessible, missing or malfunctioning "
            "and needs an issue report."
        ),
        "general_information": (
            "A general question or request for an explanation about waste management, "
            "with no actionable bin or collection need."
        ),
    },
)

QUESTIONS = {"category": CATEGORY_QUESTION}


# ---------------------------------------------------------------------------
# PolicyClassifier
# ---------------------------------------------------------------------------


class PolicyClassifier:
    """Classify a waste-management request into one of four policy categories.

    One Decider call per classify() invocation. Appends one Decision_Record to
    self.log. If confidence is below the threshold, returns low_confidence=True
    so HackathonAgent.chat() can request clarification without calling the LLM.
    """

    def __init__(self, decider: Decider, confidence_threshold: float = 0.7) -> None:
        self.decider = decider
        self.confidence_threshold = confidence_threshold
        self.log: list[dict[str, Any]] = []

    def classify(self, message: str) -> dict[str, Any]:
        """Classify *message* into a policy category.

        Returns:
          {
            "category":       str,           one of the four option keys
            "confidence":     float,         max probability across options (0-1)
            "probabilities":  dict,          {option: float} for all four options
            "decider_ms":     int,           round-trip latency in milliseconds
            "low_confidence": bool,          True when confidence < threshold
            "error":          str | None,    set only when Decider call fails
            "_record":        dict,          reference so chat() can update action_taken
          }
        """
        t0 = time.perf_counter()
        try:
            answers = self.decider.ask(message, QUESTIONS)
            decision = answers["category"]
            category = decision.label or "general_information"
            probabilities = dict(decision.probabilities)
            confidence = float(decision.confidence)
            decider_ms = round(self.decider.last_latency_ms or 0)
            low_confidence = decision.unsure(self.confidence_threshold)
            error = None
            verdict = "low_confidence" if low_confidence else "classified"
            fallback = False
        except DeciderError as exc:
            # Decider is unavailable — safe default so the agent returns clarification
            category = "general_information"
            probabilities = {
                "urgent_overflow": 0.0,
                "routine_collection": 0.0,
                "bin_issue": 0.0,
                "general_information": 0.0,
            }
            confidence = 0.0
            decider_ms = round((time.perf_counter() - t0) * 1000)
            low_confidence = True
            error = str(exc)
            verdict = "fallback"
            fallback = True

        record: dict[str, Any] = {
            "pattern": PATTERN_TAG,
            "category": category,
            "verdict": verdict,
            "probabilities": probabilities,
            "confidence": confidence,
            "decider_ms": decider_ms,
            "action_taken": "",  # filled in by HackathonAgent.chat() after routing
            "fallback": fallback,
        }
        if error:
            record["error"] = error
        self.log.append(record)

        return {
            "category": category,
            "confidence": confidence,
            "probabilities": probabilities,
            "decider_ms": decider_ms,
            "low_confidence": low_confidence,
            "error": error,
            "_record": record,  # reference so chat() can update action_taken in-place
        }
