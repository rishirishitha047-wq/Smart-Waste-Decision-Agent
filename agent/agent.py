"""EcoMind AI — Intelligent Waste Management Decision Agent.

Strands Decider 2B classifies every request into a policy category before the LLM runs.
Amazon Bedrock powers the conversational model. The classification shapes the system
prompt so the agent selects the right tools naturally.

    from agent.agent import HackathonAgent
    out = HackathonAgent().chat("A bin near the school is almost overflowing.")
    out["reply"], out["decisions"]
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import PolicyClassifier
from .tools import TOOLS

NAME = "EcoMind AI — Waste Management Decision Agent"

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

BASE_SYSTEM_PROMPT = """You are EcoMind AI, an intelligent waste-management assistant for
municipal teams, campus administrators and waste-collection coordinators.

You help users with:
- Overflowing or urgent bins: use get_bin_status then assess_collection_priority
- Routine collection planning: use assess_collection_priority then create_collection_plan
- Damaged or inaccessible bins: use get_bin_status then report_bin_issue
- General questions: answer from your knowledge without calling tools unless asked for
  specific bin data

Always be clear that all data is simulated — never claim it comes from live sensors.
Never claim a recommendation is a completed real-world action.
If you need a specific bin ID and the user has not provided one, ask for it.

Built with the AWS User Group Madurai Strands Decider hackathon kit."""

EAGER_SYSTEM_PROMPT = """You are EcoMind AI, an intelligent waste-management assistant.
Act immediately on every request. If a bin ID is missing, use BIN-001 as the default.
Always call the most relevant tools without asking for confirmation.
Built with the AWS User Group Madurai Strands Decider hackathon kit."""

CATEGORY_PROMPT_ADDITION = {
    "urgent_overflow": (
        "\nThis request has been classified as URGENT OVERFLOW. "
        "Check the bin status with get_bin_status and assess collection priority with "
        "assess_collection_priority. If a bin ID is not provided, ask the user for it."
    ),
    "routine_collection": (
        "\nThis request has been classified as ROUTINE COLLECTION. "
        "Assess bin priorities with assess_collection_priority then produce a collection "
        "plan with create_collection_plan."
    ),
    "bin_issue": (
        "\nThis request has been classified as BIN ISSUE. "
        "Check the bin status with get_bin_status then file an issue report with "
        "report_bin_issue. If a bin ID is not provided, ask the user for it."
    ),
    "general_information": (
        "\nThis request has been classified as GENERAL INFORMATION. "
        "Answer from your knowledge. Call tools only if the user explicitly asks about "
        "a specific bin or collection plan."
    ),
}


# ---------------------------------------------------------------------------
# HackathonAgent
# ---------------------------------------------------------------------------


class HackathonAgent:
    """One Strands agent per session, with policy classification wired in as a pre-step."""

    def __init__(
        self,
        decider: Decider | None = None,
        model_id: str | None = None,
        eager: bool | None = None,
    ):
        import os

        self.decider = decider or Decider()
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()
        self.classifier = PolicyClassifier(self.decider)
        self.sessions: dict[str, Agent] = {}

    def _session(self, session_id: str, system_prompt: str) -> Agent:
        if session_id not in self.sessions:
            self.sessions[session_id] = Agent(
                model=agent_model(self.model_id),
                system_prompt=system_prompt,
                tools=TOOLS,
                callback_handler=None,
            )
        return self.sessions[session_id]

    def chat(
        self,
        message: str,
        session_id: str = "default",
        images: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Classify the request, then run the Strands Agent with a category-aware prompt.

        Returns:
          {
            "reply":      str,
            "decisions":  list[dict],   one Decision_Record per Decider call
            "model_id":   str,
            "latency_ms": int,
            "agent":      str,
            "eager":      bool,
          }
        """
        t0 = time.perf_counter()

        # Step 1: classify with Strands Decider 2B
        clf = self.classifier.classify(message)
        record = clf["_record"]

        # Step 2: low confidence or Decider unavailable → ask for clarification
        if clf["low_confidence"]:
            if clf.get("error"):
                reply = (
                    "I'm having trouble reaching the decision service right now. "
                    "Could you describe your waste-management request in more detail? "
                    "For example: is there an overflowing bin, a damaged bin, or a "
                    "collection you'd like to plan?"
                )
                record["action_taken"] = "decider_unavailable: returned clarification"
            else:
                reply = (
                    "I want to make sure I help you correctly. Could you give me a "
                    "bit more detail? For example: is there a specific bin that is "
                    "overflowing or damaged, or are you looking to plan a collection route?"
                )
                record["action_taken"] = "low_confidence: returned clarification"
            return {
                "reply": reply,
                "decisions": [record],
                "model_id": self.model_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000),
                "agent": NAME,
                "eager": self.eager,
            }

        # Step 3: build category-aware system prompt
        category = clf["category"]
        if self.eager:
            system_prompt = EAGER_SYSTEM_PROMPT
        else:
            system_prompt = BASE_SYSTEM_PROMPT + CATEGORY_PROMPT_ADDITION.get(category, "")

        # Step 4: run the Strands Agent
        try:
            agent = self._session(session_id, system_prompt)
            content: Any = (
                [*image_blocks(images), {"text": message}] if images else message
            )
            result = agent(content)
            reply = strip_thinking(str(result))
            record["action_taken"] = f"ran agent with category={category}"
        except Exception as exc:  # noqa: BLE001
            reply = "Service temporarily unavailable. Please try again."
            record["action_taken"] = f"llm_error: {type(exc).__name__}: {exc}"

        return {
            "reply": reply,
            "decisions": [record],
            "model_id": self.model_id,
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "agent": NAME,
            "eager": self.eager,
        }


if __name__ == "__main__":
    import json
    import sys

    a = HackathonAgent()
    msgs = sys.argv[1:] or [
        "A garbage bin near the school is almost overflowing. What should we do?",
        "Create a collection plan for the bins that need urgent attention.",
    ]
    for msg in msgs:
        print(json.dumps(a.chat(msg), indent=2, default=str))
