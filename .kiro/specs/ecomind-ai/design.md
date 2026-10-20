# Design Document

## Overview

EcoMind AI replaces the kit's example store-support agent with an intelligent waste-management
decision agent. Every incoming request is classified by Strands Decider 2B using a `#policy`
choice question, then routed to the appropriate tools. Amazon Bedrock powers the conversational
language model. All decision logic lives in `agent/decision.py`; all tools live in
`agent/tools.py`; orchestration lives in `agent/agent.py`. The demo UI in `demo/` is extended
to show a decision panel, bin information cards and a session decision history.

---

## Architecture

```
User
 │  HTTP POST /chat
 ▼
demo/server.py
 │
 ▼
HackathonAgent.chat(message, session_id)
 │
 ├─► PolicyClassifier.classify(message)
 │    │  Decider.ask(state, {category: choice(...)})
 │    │  ◄── Strands Decider 2B
 │    └─► {category, confidence, probabilities,
 │          decider_ms, low_confidence}
 │
 │  if low_confidence ──► return clarification reply (no agent call)
 │
 ├─► Build category-aware system prompt
 │
 ├─► Strands Agent (model = Bedrock LLM, tools = TOOLS)
 │    │  agent(message)
 │    ├─► get_bin_status(bin_id)
 │    ├─► assess_collection_priority(bin_ids)
 │    ├─► create_collection_plan(vehicle_capacity)
 │    └─► report_bin_issue(bin_id, description)
 │         └─► reads agent/data/bins.json; writes in-memory ISSUES list
 │
 └─► return {reply, decisions, model_id, latency_ms, agent, eager}
         │
         └─► demo/server.py adds classification field, responds to UI
```

Design decisions:

- The PolicyClassifier runs **before** the Strands Agent. If confidence < 0.7, `chat()`
  returns a clarification reply without calling the LLM or any tool.
- The classified category is injected into the system prompt; the LLM selects tools based on
  natural-language guidance — no hard-coded if/else routing.
- The PolicyClassifier is a plain pre-processing class, not an `InterventionHandler`.
- Tools operate on in-memory data loaded once from `agent/data/bins.json`.
- All numeric calculations (fill percentages, priority scores, capacity checks) are performed
  in application code, not by Strands Decider 2B.

---

## Components and Interfaces

### PolicyClassifier (`agent/decision.py`)

```python
PATTERN_TAG = "#policy"
IS_KIT_EXAMPLE = False

CATEGORY_QUESTION = Decider.choice(
    "Which type of waste-management request is this?",
    {
        "urgent_overflow":    "A bin is overflowing, nearly full, causing a sanitation or "
                              "health concern, or needs emergency collection.",
        "routine_collection": "A request to plan, schedule or check routine waste collection "
                              "with no overflow or sanitation concern.",
        "bin_issue":          "A bin is damaged, inaccessible, missing or malfunctioning "
                              "and needs an issue report.",
        "general_information":"A general question or request for an explanation about waste "
                              "management, with no actionable bin or collection need.",
    },
)

class PolicyClassifier:
    def __init__(self, decider: Decider, confidence_threshold: float = 0.7): ...
    def classify(self, message: str) -> dict: ...
    # classify() return shape:
    # {
    #   "category":       str,    one of the four option keys
    #   "confidence":     float,
    #   "probabilities":  dict[str, float],
    #   "decider_ms":     int,
    #   "low_confidence": bool,   True when confidence < threshold
    #   "error":          str | None,  set when Decider call fails
    # }
```

Decision_Record shape (appended to `self.log` and to `chat()["decisions"]`):

```python
{
    "pattern":       "#policy",
    "category":      str,
    "verdict":       str,     # "classified" | "low_confidence" | "fallback"
    "probabilities": dict[str, float],
    "confidence":    float,
    "decider_ms":    int,
    "action_taken":  str,
    "fallback":      bool,    # True only when Decider was unavailable
}
```

Confidence handling rules:

| Condition | Action |
|---|---|
| confidence >= 0.7, any category | proceed to agent |
| confidence < 0.7, any category | return clarification; do not call agent |
| confidence >= 0.7, urgent_overflow | proceed; agent uses get_bin_status + assess_collection_priority |
| confidence < 0.7, urgent_overflow | return clarification; never treat as confirmed emergency |
| DeciderError | low_confidence=True, fallback=True; return clarification |

### HackathonAgent (`agent/agent.py`)

```python
NAME = "EcoMind AI — Waste Management Decision Agent"

class HackathonAgent:
    def __init__(self, decider=None, model_id=None, eager=None): ...
    def chat(self, message: str, session_id: str = "default",
             images: list | None = None) -> dict: ...
    # chat() return shape (unchanged kit contract):
    # {
    #   "reply":      str,
    #   "decisions":  list[dict],   one Decision_Record per Decider call
    #   "model_id":   str,
    #   "latency_ms": int,
    #   "agent":      str,
    #   "eager":      bool,
    # }
```

`chat()` flow:

1. `classifier_result = self.classifier.classify(message)`
2. Build Decision_Record from `classifier_result`
3. If `classifier_result["low_confidence"]`: return clarification reply immediately
4. Build category-aware system prompt
5. `agent = self._session(session_id, system_prompt)`
6. `result = agent(message)`
7. `reply = strip_thinking(str(result))`
8. Update `decision_record["action_taken"]`
9. Return full chat dict

System prompt template:

```python
BASE_SYSTEM_PROMPT = """You are EcoMind AI, an intelligent waste-management assistant for
municipal teams, campus administrators and waste-collection coordinators.
Always be clear that data is simulated. Never claim a recommendation is a completed action.
Built with the AWS User Group Madurai Strands Decider hackathon kit."""

CATEGORY_PROMPT_ADDITION = {
    "urgent_overflow":    "This request is about an urgent overflow. Check bin status and assess priority.",
    "routine_collection": "This request is about routine collection planning. Assess priorities and create a plan.",
    "bin_issue":          "This request is about a bin issue. Check bin status and file an issue report.",
    "general_information":"This is a general information request. Answer from knowledge; call tools only if asked for specific bin data.",
}
```

### Tools (`agent/tools.py`)

**`get_bin_status(bin_id: str) -> dict`**

```
Validate: bin_id non-empty/non-null  →  {"error": "bin_id is required"}
Lookup bins.json by id (case-insensitive strip)
Not found  →  {"error": f"bin '{bin_id}' not found"}
Success    →  {bin_id, fill_level, location, waste_type,
               last_collected, issue_status, distance_meters, data_source: "simulated"}
```

**`assess_collection_priority(bin_ids: list[str] | None = None) -> dict`**

Priority formula (all application code):

```
hours_since     = (now_utc - last_collected).total_seconds() / 3600
capped_hours    = min(hours_since, 72)
priority_score  = round(fill_level * 0.7 + (capped_hours / 72) * 100 * 0.3, 1)
overflow        = fill_level >= config["overflow_threshold"]   # default 90
```

Returns bins sorted descending by `priority_score`.

**`create_collection_plan(vehicle_capacity: int | None = None) -> dict`**

```
vehicle_capacity < 1  →  {"error": "vehicle_capacity must be at least 1"}
capacity = vehicle_capacity or config["vehicle_capacity"]  # default 5
assessed = all bins sorted by priority desc, then distance_meters asc
plan = assessed[:capacity]
return {recommendation: True, plan: [...], total_bins_assessed, capacity_used,
        note: "This is a recommendation only. No real dispatch has occurred.",
        data_source: "simulated"}
```

**`report_bin_issue(bin_id: str, description: str, issue_type: str = "general") -> dict`**

```
bin_id empty/null          →  {"error": "bin_id is required"}
bin_id not in bins.json    →  {"error": f"bin '{bin_id}' not found"}
len(description) not 1-500 →  {"error": "description must be between 1 and 500 characters"}
Dedup: existing open issue with same bin_id + description (case-insensitive)
  →  return existing record + {"duplicate": True}
report_id = f"RPT-{bin_id.upper()}-{int(time.time())}"
Append to module-level ISSUES list
return {report_id, bin_id, description, issue_type, status: "open",
        created_at: ISO8601, duplicate: False}
```

`ISSUES` is a module-level list (in-memory; resets on process restart; clearly labelled as simulated).

```python
TOOLS = [get_bin_status, assess_collection_priority,
         create_collection_plan, report_bin_issue]
```

### Demo Server (`demo/server.py`)

New endpoint:

```
GET /bins  →  {"bins": [...bins.json...], "data_note": "Simulated data only."}
```

Extended `POST /chat` response (adds field, preserves existing shape):

```json
{
  "reply": "...",
  "decisions": [...],
  "model_id": "...",
  "latency_ms": 123,
  "classification": {
    "category":       "urgent_overflow",
    "confidence":     0.91,
    "low_confidence": false
  }
}
```

### Demo UI (`demo/static/index.html`)

EcoMind AI heading and tagline. Sustainability colour scheme:

| Variable | Value | Use |
|---|---|---|
| `--primary` | `#2d6a4f` | Header, buttons |
| `--accent` | `#95d5b2` | Highlights, borders |
| `--bg` | `#f0f7f4` | Page background |
| `--urgent` | `#d62828` | urgent_overflow badge |
| `--routine` | `#2d6a4f` | routine_collection badge |
| `--issue` | `#e76f51` | bin_issue badge |
| `--info` | `#457b9d` | general_information badge |

New panels added to the existing layout:

- **Decision panel**: category badge, confidence progress bar, latency, action taken.
- **Clarification banner**: yellow `⚠ Needs clarification` strip when `low_confidence == true`.
- **Bin info card**: fill gauge, waste type, location, issue status.
- **Collection plan card**: ranked list with fill indicators and overflow flags.
- **Issue report card**: report ID, bin, description, status badge.
- **Decision history sidebar**: last 10 decisions per session (timestamp, category badge, confidence).

---

## Data Models

### `agent/data/bins.json`

Array of bin objects. Schema:

```
{
  "id":              string,              // BIN-001 … BIN-010
  "fill_level":      integer (0–100),     // percentage full
  "location":        string,              // human-readable description
  "waste_type":      string,              // general | recyclable | organic | hazardous
  "last_collected":  string (ISO 8601),   // UTC datetime
  "issue_status":    string,              // none | damaged | inaccessible | missing
  "distance_meters": integer              // estimated distance from depot
}
```

Ten example records (representative states):

| id | fill_level | issue_status | Notes |
|---|---|---|---|
| BIN-001 | 95 | none | Overflowing |
| BIN-002 | 88 | none | Near-overflow |
| BIN-003 | 45 | none | Routine |
| BIN-004 | 12 | none | Recently collected |
| BIN-005 | 72 | none | Routine |
| BIN-006 | 60 | none | Routine |
| BIN-007 | 30 | damaged | Issue — damaged |
| BIN-008 | 55 | inaccessible | Issue — inaccessible |
| BIN-009 | 8  | none | Recently collected |
| BIN-010 | 91 | none | Overflowing |

### `agent/data/config.json`

```json
{
  "overflow_threshold": 90,
  "vehicle_capacity":   5,
  "data_note":          "Simulated data only. Not from live sensors or real-time telemetry.",
  "last_updated":       "2025-01-10"
}
```

### `agent/eval_cases.jsonl`

One JSON object per line:

```json
{"split": "tune|test", "input": "...", "expected_category": "...", "notes": "..."}
```

24 total: 14 tune cases (3 urgent_overflow, 3 routine_collection, 3 bin_issue, 2 general_information,
2 ambiguous/borderline, 1 low-information) and 10 test cases (2 per main category + 1 ambiguous
+ 1 tricky wording).

---

## Error Handling

| Failure | Detection point | Response |
|---|---|---|
| Decider unreachable | `DeciderError` in `classify()` | `low_confidence=True, fallback=True`; chat returns clarification; Decision_Record labelled `"fallback": True` |
| Bedrock unavailable | exception in Strands `agent()` | `{"reply": "Service temporarily unavailable. Please try again.", "decisions": [...]}` |
| Empty/null `bin_id` | validation at top of each tool | `{"error": "bin_id is required"}` |
| Unknown `bin_id` | lookup miss in bins.json | `{"error": "bin '{id}' not found"}` |
| Invalid description length | validation in `report_bin_issue` | `{"error": "description must be between 1 and 500 characters"}` |
| Duplicate open issue | dedup check in `report_bin_issue` | returns existing record + `"duplicate": True` |
| `vehicle_capacity` < 1 | validation in `create_collection_plan` | `{"error": "vehicle_capacity must be at least 1"}` |
| Fallback classification used | `fallback=True` flag | always labelled; never presented as a real Decider decision |

---

## Correctness Properties

### Property 1: Single Decider call per chat turn

**Validates: Requirements 1.3**

Strands Decider 2B is called exactly once per `chat()` invocation, for the policy
classification only. All arithmetic (fill %, priority scores, capacity checks) is computed
in application code.

### Property 2: No silent emergencies

**Validates: Requirements 9.1, 9.2**

A request classified as `urgent_overflow` with confidence < 0.7 must always produce a
clarification reply. The agent must never automatically dispatch or confirm an emergency
action without sufficient confidence.

### Property 3: Recommendation labelling

**Validates: Requirements 6.3**

`create_collection_plan` always includes `"recommendation": True` and the note string.
The agent's system prompt reinforces that recommendations are not completed real-world actions.

### Property 4: Simulated data labelling

**Validates: Requirements 10.2, 10.3**

All tool responses include `"data_source": "simulated"`. The UI shows the `data_note` from
`config.json`. The agent never claims to have sensor readings, live traffic data or real dispatches.

### Property 5: No hardcoded secrets

**Validates: Requirements 12.1, 12.2**

Credentials are read exclusively from `.env` via `decider_kit.config`. `.env.example`
contains only placeholder values. No secrets appear in source code or committed files.

### Property 6: Kit contract preserved

**Validates: Requirements 8.3, 15.5**

`HackathonAgent.chat()` returns exactly `{reply, decisions, model_id, latency_ms, agent, eager}`.
The `decisions` list contains exactly one Decision_Record per Decider call.

### Property 7: IS_KIT_EXAMPLE removed

**Validates: Requirements 15.1**

`agent/decision.py` sets `IS_KIT_EXAMPLE = False`. The submission check will not fail on this flag.

### Property 8: REUSABLE DECISION PATTERN header

**Validates: Requirements 15.2**

The module docstring in `agent/decision.py` carries `PATTERN_TAG = "#policy"` under the
`REUSABLE DECISION PATTERN` header so the kit's submission check finds it.

---

## Testing Strategy

### Unit tests (`tests/`)

- Each tool called with valid, invalid and boundary inputs.
- `assess_collection_priority` priority formula verified against known values.
- `create_collection_plan` capacity slicing and ordering verified.
- `report_bin_issue` deduplication path and duplicate flag.
- `PolicyClassifier.classify()` with mocked Decider returning each category.
- `PolicyClassifier.classify()` with mocked Decider returning confidence < 0.7.
- `PolicyClassifier.classify()` when Decider raises `DeciderError`.
- `HackathonAgent.chat()` return shape verified field-by-field.

### Evaluation benchmark (`./kit bench`)

Run against `agent/eval_cases.jsonl`:

- Tune split: used to verify and refine the `CATEGORY_QUESTION` option descriptions.
- Test split: held out; accuracy, latency and confidence reported after tuning is complete.
- Actual numbers recorded in `results/benchmark.md`; no fabricated results.

### End-to-end demo verification

- `./kit demo` starts the server; four scenarios from `agent/demo_script.yaml` exercised manually:
  urgent overflow, routine collection plan, bin issue report, general question.
- AWS deployment: same four scenarios run against the deployed endpoint.

---

## File Map

| File | Change |
|---|---|
| `agent/decision.py` | Replace: PolicyClassifier, CATEGORY_QUESTION, PATTERN_TAG="#policy", IS_KIT_EXAMPLE=False |
| `agent/agent.py` | Replace: EcoMind AI agent, category-aware prompts, PolicyClassifier pre-step |
| `agent/tools.py` | Replace: 4 waste-management tools, in-memory ISSUES list, loads bins.json |
| `agent/AGENT.md` | Update: project name, users, decision pattern, tools, model config |
| `agent/eval_cases.jsonl` | Replace: 24 waste-management eval cases (tune + test splits) |
| `agent/demo_script.yaml` | Replace: EcoMind AI demo scenarios |
| `agent/features.yaml` | Trim to only needed AgentCore features |
| `demo/server.py` | Add GET /bins; extend POST /chat response with classification field |
| `demo/static/index.html` | Add heading, decision panel, sustainability theme, history sidebar |
| `agent/data/bins.json` | **New**: 10 simulated bin records |
| `agent/data/config.json` | **New**: overflow threshold, vehicle capacity, data note |
| `decider_kit/` | **Unchanged** |
| `deploy/` | **Unchanged** |
| `docs/` | **Unchanged** |
| `.kiro/steering/` | **Unchanged** |

---

*Built with the AWS User Group Madurai Strands Decider hackathon kit*



