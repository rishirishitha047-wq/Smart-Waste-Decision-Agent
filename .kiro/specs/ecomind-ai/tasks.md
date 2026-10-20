# Implementation Plan

## Overview

Replace the kit's example store-support agent with EcoMind AI — an intelligent waste-management
decision agent. The implementation proceeds in 13 task groups: scaffold and data, policy
classifier, tools, agent wiring, evaluation cases, demo server, demo UI, demo script,
unit tests, benchmark tuning, end-to-end verification, AWS deployment, and submission materials.

## Task Dependency Graph

```json
{
  "waves": [
    {"wave": 1, "tasks": ["1"]},
    {"wave": 2, "tasks": ["2"]},
    {"wave": 3, "tasks": ["3"]},
    {"wave": 4, "tasks": ["4"]},
    {"wave": 5, "tasks": ["5", "6", "8", "9"]},
    {"wave": 6, "tasks": ["7", "10"]},
    {"wave": 7, "tasks": ["11"]},
    {"wave": 8, "tasks": ["12"]},
    {"wave": 9, "tasks": ["13"]}
  ],
  "dependencies": {
    "2":  ["1"],
    "3":  ["2"],
    "4":  ["3"],
    "5":  ["4"],
    "6":  ["4"],
    "7":  ["6"],
    "8":  ["4"],
    "9":  ["4"],
    "10": ["5", "9"],
    "11": ["7", "8"],
    "12": ["11"],
    "13": ["10", "12"]
  }
}
```

## Tasks
- [x] 1. Project scaffold and data files
  - [x] 1.1 Create `agent/data/` directory and write `bins.json` with 10 simulated bin records (2 overflowing ≥90%, 1 near-overflow 88%, 2 with issues, 3 routine, 2 recently collected)
  - [x] 1.2 Write `agent/data/config.json` with `overflow_threshold`, `vehicle_capacity` and `data_note`
  - [x] 1.3 Update `agent/AGENT.md` with EcoMind AI project name, user personas, policy decision description, tool list and model config
  - _Requirements: 10.1, 10.3, 15.1_

- [x] 2. Policy classifier (`agent/decision.py`)
  - [x] 2.1 Replace file with `REUSABLE DECISION PATTERN: policy classification (#policy)` docstring; set `PATTERN_TAG = "#policy"` and `IS_KIT_EXAMPLE = False`
  - [x] 2.2 Define `CATEGORY_QUESTION` using `Decider.choice()` with four options: `urgent_overflow`, `routine_collection`, `bin_issue`, `general_information`, each with a precise one-line description
  - [x] 2.3 Implement `PolicyClassifier.__init__(decider, confidence_threshold=0.7)` and `classify(message) -> dict` returning `{category, confidence, probabilities, decider_ms, low_confidence, error}`
  - [x] 2.4 Append one Decision_Record `{pattern, category, verdict, probabilities, confidence, decider_ms, action_taken, fallback}` to `self.log` per call
  - [x] 2.5 Handle `DeciderError` in `classify()`: set `low_confidence=True`, `fallback=True`, `error=str(e)`; return `general_information` as safe default
  - _Requirements: 1.1, 1.2, 2.1–2.5, 8.1, 8.2, 9.1, 9.2, 11.2, 12.3, 15.2_

- [x] 3. Agent tools (`agent/tools.py`)
  - [x] 3.1 Implement `get_bin_status(bin_id: str) -> dict`: validate non-empty/non-null input; look up `bins.json`; return full bin record with `data_source: "simulated"` or structured error
  - [x] 3.2 Implement `assess_collection_priority(bin_ids: list[str] | None = None) -> dict`: load bins, compute `priority_score = fill_level * 0.7 + min(hours_since, 72) / 72 * 100 * 0.3`, set `overflow = fill_level >= config["overflow_threshold"]`, return sorted descending list
  - [x] 3.3 Implement `create_collection_plan(vehicle_capacity: int | None = None) -> dict`: validate capacity ≥ 1; sort all bins by priority desc then distance asc; slice to capacity; return with `recommendation: True` and disclaimer note
  - [x] 3.4 Implement `report_bin_issue(bin_id: str, description: str, issue_type: str = "general") -> dict`: validate inputs; check for duplicate open issue (same bin_id + description case-insensitive + status open); generate `RPT-{BIN_ID}-{timestamp}` report ID; append to module-level `ISSUES` list
  - [x] 3.5 Collect `TOOLS = [get_bin_status, assess_collection_priority, create_collection_plan, report_bin_issue]`
  - _Requirements: 4.1–4.4, 5.1–5.3, 6.1–6.4, 7.1–7.4_

- [x] 4. EcoMind AI agent (`agent/agent.py`)
  - [x] 4.1 Replace file: set `NAME = "EcoMind AI — Waste Management Decision Agent"`; define `BASE_SYSTEM_PROMPT` and `CATEGORY_PROMPT_ADDITION` dict for all four categories
  - [x] 4.2 Implement `HackathonAgent.__init__`: create `self.classifier = PolicyClassifier(self.decider)`, `self.sessions: dict[str, Agent] = {}`
  - [x] 4.3 Implement `chat()` flow: (1) `classify(message)` → (2) if `low_confidence` return clarification immediately → (3) build category-aware system prompt → (4) call Strands Agent → (5) return `{reply, decisions, model_id, latency_ms, agent, eager}`
  - [x] 4.4 Implement `_session(session_id, system_prompt)`: create `Agent(model=agent_model(self.model_id), system_prompt=..., tools=TOOLS, callback_handler=None)` on first use; store in `self.sessions`
  - [x] 4.5 Handle Bedrock/LLM unavailability: catch exception from `agent(message)`; return `{"reply": "Service temporarily unavailable. Please try again.", "decisions": [...], ...}`
  - _Requirements: 8.3, 8.4, 9.1–9.3, 11.1, 11.3, 11.4, 15.5_

- [x] 5. Evaluation cases (`agent/eval_cases.jsonl`)
  - [x] 5.1 Write 14 tune-split cases covering: 3 `urgent_overflow`, 3 `routine_collection`, 3 `bin_issue`, 2 `general_information`, 2 ambiguous/borderline, 1 low-information single word
  - [x] 5.2 Write 10 test-split cases covering: 2 `urgent_overflow`, 2 `routine_collection`, 2 `bin_issue`, 2 `general_information`, 1 ambiguous, 1 tricky-wording
  - [x] 5.3 Each line: `{"split": "tune"|"test", "input": str, "expected_category": str, "notes": str}`
  - _Requirements: 14.1, 14.2, 14.3, 14.6_

- [x] 6. Demo server (`demo/server.py`)
  - [x] 6.1 Add `GET /bins` endpoint returning `{"bins": [...], "data_note": "Simulated data only."}`
  - [x] 6.2 Extend `POST /chat` response to include `"classification": {category, confidence, low_confidence}` field extracted from `decisions[0]`
  - _Requirements: 13.4, 13.7_

- [x] 7. Demo UI (`demo/static/index.html`)
  - [x] 7.1 Add EcoMind AI heading (`🌿 EcoMind AI`) and tagline; apply sustainability colour scheme (`--primary: #2d6a4f`, `--accent: #95d5b2`, `--bg: #f0f7f4`)
  - [x] 7.2 Add decision panel: category badge colour-coded by category, confidence progress bar, latency display, action taken text
  - [x] 7.3 Add clarification banner: yellow `⚠ Needs clarification` strip shown when `low_confidence == true`
  - [x] 7.4 Add bin info card: fill-level gauge, waste type, location, issue status
  - [x] 7.5 Add collection plan card: ranked list with fill indicators and overflow flags; plan disclaimer label
  - [x] 7.6 Add issue report card: report ID, bin ID, description, status badge, duplicate indicator
  - [x] 7.7 Add decision history sidebar: last 10 decisions per session (timestamp, category badge, confidence)
  - [x] 7.8 Ensure accessible controls, clear loading states and understandable error messages
  - _Requirements: 13.1–13.9_

- [x] 8. Demo script and features (`agent/demo_script.yaml`, `agent/features.yaml`)
  - [x] 8.1 Rewrite `agent/demo_script.yaml` with four EcoMind AI scenarios: urgent overflow at named location, routine collection plan, damaged bin report, general information question
  - [x] 8.2 Update `agent/features.yaml` to retain only the AgentCore features actually used by EcoMind AI
  - _Requirements: 15.1_

- [x] 9. Unit tests (`tests/`)
  - [x] 9.1 Write tests for `get_bin_status`: valid id, unknown id, empty id, null id
  - [x] 9.2 Write tests for `assess_collection_priority`: known priority formula values, overflow flag at threshold, ordering
  - [x] 9.3 Write tests for `create_collection_plan`: capacity slicing, ordering by priority then distance, capacity < 1 error, empty bin list
  - [x] 9.4 Write tests for `report_bin_issue`: valid report, unknown bin, empty description, description > 500 chars, duplicate open issue
  - [x] 9.5 Write tests for `PolicyClassifier.classify()`: each category (mocked Decider), low-confidence path, DeciderError fallback
  - [x] 9.6 Write tests for `HackathonAgent.chat()`: return shape, decisions list, low_confidence short-circuit, LLM unavailability
  - [x] 9.7 Run `./kit test` (or equivalent); record results honestly — do not suppress failures
  - _Requirements: 14.3, 14.5_

- [x] 10. Benchmark and tuning
  - [x] 10.1 Run `./kit bench --split tune` against the 14 tune cases; record accuracy, latency and confidence
  - [x] 10.2 Adjust `CATEGORY_QUESTION` option descriptions as needed based on tune results; re-run until tune accuracy is satisfactory
  - [x] 10.3 Run `./kit bench --split test` against the 10 held-out test cases; record final accuracy, latency, confidence and any errors honestly
  - _Requirements: 14.4, 14.6_

- [x] 11. End-to-end demo verification
  - [x] 11.1 Run `./kit demo`; exercise all four scenarios from `demo_script.yaml`; confirm decision panel, bin cards, recommendation cards and issue report cards render correctly
  - [x] 11.2 Confirm clarification banner appears for a deliberately vague message
  - [x] 11.3 Confirm decision history sidebar updates after each turn
  - _Requirements: 13.1–13.9, 15.4_

- [x] 12. AWS deployment and verification
  - [x] 12.1 Run `./kit deploy` (or the kit's deployment command); confirm EcoMind AI is deployed to AWS with Amazon Bedrock as the LLM provider
  - [x] 12.2 Exercise the same four demo scenarios against the deployed endpoint; record results
  - [x] 12.3 Confirm `IS_KIT_EXAMPLE = False` and `PATTERN_TAG = "#policy"` pass the kit's submission checks
  - _Requirements: 11.3, 15.4_

- [x] 13. README and submission materials
  - [x] 13.1 Run the kit's README generation command to update `README.md`; verify kit attribution line is present
  - [x] 13.2 Record benchmark results in `results/benchmark.md` (actual numbers from task 10, no fabrication)
  - [x] 13.3 Run `./kit check` (or equivalent submission checker); fix every blocking failure
  - [x] 13.4 Prepare public GitHub repository: confirm no secrets in committed files; update `.env.example` with placeholders only
  - _Requirements: 12.2, 14.4, 14.5, 15.3, 15.4_

## Notes

- Run `./kit test` after task 9 before proceeding to task 10.
- Run `./kit bench --split tune` in task 10.1 and `./kit bench --split test` in task 10.3.
  Report actual numbers; do not fabricate results.
- The kit's submission checker (`./kit check`) must pass with zero blocking failures before
  task 13 is considered complete.
- Keep `decider_kit/`, `deploy/`, `docs/` and `.kiro/steering/` unchanged throughout.
- All credentials must remain in `.env` (git-ignored). Never commit real credentials.

