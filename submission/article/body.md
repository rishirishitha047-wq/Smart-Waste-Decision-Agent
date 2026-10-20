# EcoMind AI: A Waste Management Decision Agent Powered by Strands Decider 2B

By Rishitha Senthilkumar

Municipal waste teams receive dozens of requests a day: overflowing bins near schools, damaged containers in residential areas, routine collection schedules, and general questions about recycling. Most of these are language problems first and data problems second. A human dispatcher reads the request, decides what kind of action it needs, and only then checks the data. EcoMind AI automates that first decision. It uses Strands Decider 2B to classify every incoming request into one of four policy categories before any tool runs, then routes to the right workflow. In testing, the decider reached 91.7% accuracy at 5.9x the speed of the LLM baseline.

## The project

EcoMind AI serves three user groups: municipal teams managing waste across city zones, campus administrators handling university or hospital grounds, and waste-collection coordinators planning dispatch routes. Users type a natural-language request into a chat interface and the agent responds with bin status, priority assessments, collection plans, or issue reports.

The agent has four tools: get_bin_status retrieves a bin's fill level, location, waste type and issue status from simulated data; ssess_collection_priority calculates a numeric priority score for each bin based on fill level and time since last collection; create_collection_plan produces a ranked collection order within vehicle capacity limits; eport_bin_issue creates a simulated issue report with deduplication for repeat complaints.

The demo UI shows a sustainability-themed chat panel with a decision sidebar. Every turn displays the classified category as a colour-coded badge, a confidence bar, the decider latency, and a history of recent decisions. When the decider is unsure, a yellow clarification banner appears instead of an action.

< FIGURE 1 of 2: upload submission/article/img/architecture.png here >
Alt text: Architecture diagram showing the user, the Strands Agent with tools and policy decision, Amazon Bedrock, and Strands Decider 2B

## How I built it

The agent runs on Strands Agents with Amazon Bedrock as the generative model. The architecture is straightforward: the user sends a message, the PolicyClassifier calls Strands Decider 2B once to classify the request, and the classified category is injected into the system prompt. The Strands Agent then runs with category-aware instructions so it selects the right tools naturally, without hard-coded if/else routing.

All decision logic lives in gent/decision.py, all tools in gent/tools.py, and the orchestration in gent/agent.py. The data is 10 simulated bins stored in gent/data/bins.json with varied fill levels, issue states and distances. The spec-driven build used Kiro to create requirements, design and tasks documents under .kiro/specs/ecomind-ai/ before any code was written.

The decision does not use an InterventionHandler. The PolicyClassifier runs as a pre-processing step before the Strands Agent is invoked, which keeps the classification fast and the agent loop clean.

## The decision I handed to Strands Decider 2B

Every incoming request needs one decision before any tool runs: what kind of request is this? This is a policy classification problem, not an arithmetic problem. Fill percentages, priority scores and capacity checks are all computed in application code. The decider only sees the language.

The typed question is a single choice with four options:

`python
QUESTIONS = {"category": Decider.choice(
    "Which type of waste-management request is this?",
    {
        "urgent_overflow": "A bin is overflowing, nearly full, causing a sanitation or health concern, or needs emergency collection.",
        "routine_collection": "A request to plan, schedule or check routine waste collection with no overflow or sanitation concern.",
        "bin_issue": "A bin is damaged, inaccessible, missing or malfunctioning and needs an issue report.",
        "general_information": "A general question or request for an explanation about waste management, with no actionable bin or collection need.",
    },
)}
`

When the decider returns a category with confidence above 0.7, the agent builds a category-aware system prompt and runs the Strands Agent. When confidence is below 0.7, the agent returns a clarification reply without calling any tool. For urgent_overflow specifically, low confidence always means clarification, never an auto-confirmed emergency. This is the key safety property: an uncertain classification is never treated as a confirmed crisis.

## Measured

The benchmark ran 24 labelled cases (14 tune, 10 held-out test) through both Strands Decider 2B and the qwen3.5-4b LLM baseline, answering the same choice question.

| | Strands Decider 2B | qwen3.5-4b |
|---|---|---|
| Accuracy | 91.7% | 79.2% |
| Latency p50 per decision | 1814 ms | 10684 ms |
| Latency p95 | 2420 ms | 11609 ms |
| Cost per 1,000 decisions | \.0350 | \.0000 |
| Answered alone at confidence >= 0.7 | 79% | 100% |
| Accuracy when confident | 94.7% | 79.2% |

< FIGURE 2 of 2: upload submission/article/img/bench-accuracy.png here >
Alt text: Bar chart comparing accuracy of Strands Decider 2B and the LLM baseline on 24 labelled cases

The decider ran on the AWS User Group Madurai hosted API (strands-decider-2b-hobson-v19). The LLM baseline ran on the same hosted cloud (qwen3.5-4b, free during the hackathon, hence the zero cost).

The decider was more accurate (91.7% vs 79.2%) and 5.9x faster at the median (1814 ms vs 10684 ms). The trade-off is confidence: the decider sent 21% of cases to clarification at the 0.7 threshold, while the LLM answered everything. But when the decider was confident, its accuracy rose to 94.7%, higher than the LLM's 79.2%. The cost difference is small: \.035 per 1,000 decisions for the hosted decider versus \ for the free hackathon LLM, though the LLM's latency and token costs would be higher in production.

## The reusable decision pattern

The pattern lives in gent/decision.py under the REUSABLE DECISION PATTERN: policy classification (#policy) header. To reuse it in another agent, copy the file, replace CATEGORY_QUESTION with your own taxonomy, and adjust the confidence threshold. The classifier returns a structured record with the category, probabilities, confidence, latency and a verdict, so the calling agent can log, display and branch on the result.

The wiring is three lines in the agent's chat() method: call classify(), check low_confidence, and build a category-aware system prompt. No InterventionHandler, no middleware, no framework-specific hooks.

## What I learned and what is next

The biggest lesson was that a fast, calibrated decision model is better than a large LLM for routing. The decider's 94.7% accuracy-when-confident beats the LLM's 79.2%, and it does so in under 2 seconds. The 21% of cases it sends to clarification are the right ones to send: ambiguous, low-information requests where acting would be worse than asking.

The BOM in the .env file was a subtle bug. The UTF-8 byte-order mark made load_dotenv() read the first key as a corrupted string, silently falling back to local mode and sending requests to the wrong API endpoint. Stripping the BOM fixed it instantly.

Next steps: add a second decider question for urgency scoring (how urgent is this overflow on a 1-5 scale), wire the collection plan to real route optimisation, and deploy to Amazon Bedrock AgentCore Runtime for production use.

---

Code: https://github.com/rishirishitha047-wq/Smart-Waste-Decision-Agent . Video: (upload demo.mp4 to YouTube, then paste the link here) . Tags: #strands-decider-2b #policy

Built with the AWS User Group Madurai Strands Decider hackathon kit.