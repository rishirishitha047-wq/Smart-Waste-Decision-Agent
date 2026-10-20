# EcoMind AI — Intelligent Waste Management Decision Agent

## Project

EcoMind AI is an intelligent waste-management decision agent for the AWS Agent Experience Hackathon: Strands Decider. It helps municipal teams, campus administrators and waste-collection coordinators decide what to do about overflowing bins, collection requests, sanitation issues and routine waste-management questions.

## Users

- **Municipal teams**: city or council staff managing waste collection across multiple zones
- **Campus administrators**: university, school or hospital grounds managers
- **Waste-collection coordinators**: dispatch staff planning and scheduling collection routes

## The Strands Decider Decision

**Pattern**: Policy classification (`#policy`)

EcoMind AI classifies every incoming request with Strands Decider 2B into one of four categories:

| Category | Description |
|---|---|
| `urgent_overflow` | A bin is overflowing, nearly full, or causing a sanitation/health concern |
| `routine_collection` | A request to plan, schedule or check routine waste collection |
| `bin_issue` | A bin is damaged, inaccessible, missing or malfunctioning |
| `general_information` | A general question or explanation request about waste management |

The classified category is injected into the agent's system prompt to guide tool selection. If confidence is below 0.7, the agent asks for clarification rather than acting — especially for `urgent_overflow`, which is never auto-confirmed at low confidence.

## Tools

| Tool | Description |
|---|---|
| `get_bin_status` | Retrieve a bin's recorded condition, fill level, location and issue status |
| `assess_collection_priority` | Calculate risk and collection priority scores from bin records |
| `create_collection_plan` | Recommend a collection order by urgency, distance and vehicle capacity |
| `report_bin_issue` | Create a simulated issue report and return its report ID |

## Data

Realistic synthetic data is stored in `agent/data/bins.json` (10 bins) and `agent/data/config.json` (overflow threshold: 90%, vehicle capacity: 5). All data is clearly labelled as simulated. No live sensor readings, traffic data or real dispatches are invented.

## Model Configuration

- **Decision model**: Strands Decider 2B (via `decider_kit.Decider`)
- **Language model**: Amazon Bedrock (default: `amazon.nova-pro-v1:0`); configurable via `LLM_PROVIDER` and `BEDROCK_MODEL_ID` in `.env`
- **Fallback**: local Ollama or AWS User Group Madurai cloud (see `.env.example`)

## Decision Record

Every `chat()` call returns a `decisions` list with one record per Decider call:

```json
{
  "pattern":       "#policy",
  "category":      "urgent_overflow",
  "verdict":       "classified",
  "probabilities": {"urgent_overflow": 0.91, "routine_collection": 0.04, "bin_issue": 0.03, "general_information": 0.02},
  "confidence":    0.91,
  "decider_ms":    142,
  "action_taken":  "ran agent with category=urgent_overflow",
  "fallback":      false
}
```

## Attribution

Built with the AWS User Group Madurai Strands Decider hackathon kit.
