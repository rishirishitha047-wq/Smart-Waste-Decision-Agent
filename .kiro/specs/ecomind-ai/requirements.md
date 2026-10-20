# Requirements Document

## Introduction

EcoMind AI is an intelligent waste-management decision agent built inside the AWS User Group
Madurai Strands Decider hackathon kit. It serves municipal teams, campus administrators and
waste-collection coordinators who need to decide what to do about overflowing bins, collection
requests, sanitation concerns, damaged bins and routine waste-management questions. The agent
hands exactly one decision to Strands Decider 2B: classifying the user's natural-language
request into one of four policy categories. The classification drives which tool or workflow
runs. Amazon Bedrock powers the conversational part. Every decision produces a structured record
with the chosen category, confidence, latency and action taken. The project preserves the
kit's `HackathonAgent.chat()` contract, the reusable decision-pattern labelling, and the kit
attribution line.

## Glossary

- **EcoMind_Agent**: The `HackathonAgent` that powers EcoMind AI, exposing
  `chat(message, session_id="default", images=None) -> dict`.
- **Decider**: Strands Decider 2B, the decision model accessed through the `decider_kit`
  `Decider` client and its typed-question API.
- **Policy_Classifier**: The reusable decision pattern tagged `#policy` in `agent/decision.py`
  that calls the Decider to classify a request into a Policy_Category.
- **Policy_Category**: One of `urgent_overflow`, `routine_collection`, `bin_issue` or
  `general_information`.
- **Decision_Record**: A structured dict appended to the `decisions` list returned by `chat()`,
  recording one Decider call.
- **Demo_UI**: The web application in `demo/` served by `./kit demo`.
- **Bin_Records**: The simulated waste-management data stored under `agent/data/`.
- **Amazon_Bedrock**: The managed generative LLM service that powers the EcoMind_Agent's
  conversation.
- **get_bin_status**: The tool that retrieves a bin's recorded condition and location.
- **assess_collection_priority**: The tool that calculates risk and collection priority from
  Bin_Records.
- **create_collection_plan**: The tool that recommends a collection order based on urgency,
  distance estimates and vehicle capacity.
- **report_bin_issue**: The tool that creates a simulated issue report and returns its report
  ID.
- **Tune_Split**: The subset of evaluation cases used to refine the Policy_Classifier questions.
- **Test_Split**: The held-out subset of evaluation cases used to report accuracy.

## Requirements

### Requirement 1: Policy classification decision

**User Story:** As a waste-collection coordinator, I want the EcoMind_Agent to classify my
request into the correct category, so that the EcoMind_Agent selects the right workflow.

#### Acceptance Criteria

1. WHEN a user submits a natural-language waste-management request, THE Policy_Classifier SHALL
   call the Decider with a single `choice` question whose four options are `urgent_overflow`,
   `routine_collection`, `bin_issue` and `general_information`.
2. THE Policy_Classifier SHALL pass the full user message as the state to the Decider in one
   call.
3. THE EcoMind_Agent SHALL compute fill percentages, overflow thresholds, vehicle capacity and
   numeric priority scores using application code rather than the Decider.

### Requirement 2: Policy category definitions

**User Story:** As a municipal team member, I want each category to mean something specific, so
that the EcoMind_Agent responds consistently.

#### Acceptance Criteria

1. THE Policy_Classifier SHALL define the `urgent_overflow` option as a request indicating a
   potentially urgent overflow or sanitation concern.
2. THE Policy_Classifier SHALL define the `routine_collection` option as a request for normal
   collection planning or scheduling.
3. THE Policy_Classifier SHALL define the `bin_issue` option as a request about a damaged,
   inaccessible or malfunctioning bin.
4. THE Policy_Classifier SHALL define the `general_information` option as a general question or
   a request for an explanation.

### Requirement 3: Tool routing from classification

**User Story:** As a campus administrator, I want the EcoMind_Agent to run the right tool for my
request, so that I receive a useful response.

#### Acceptance Criteria

1. WHEN the Policy_Classifier classifies a request as `urgent_overflow`, THE EcoMind_Agent SHALL
   run `get_bin_status` and `assess_collection_priority`.
2. WHEN the Policy_Classifier classifies a request as `routine_collection`, THE EcoMind_Agent
   SHALL run `assess_collection_priority` and `create_collection_plan`.
3. WHEN the Policy_Classifier classifies a request as `bin_issue`, THE EcoMind_Agent SHALL run
   `get_bin_status` and `report_bin_issue`.
4. WHEN the Policy_Classifier classifies a request as `general_information`, THE EcoMind_Agent
   SHALL answer the question from the conversation.

### Requirement 4: get_bin_status tool

**User Story:** As a waste-collection coordinator, I want to look up a bin's recorded condition
and location, so that I know the current state of the bin.

#### Acceptance Criteria

1. WHEN `get_bin_status` is called with a valid bin identifier, THE `get_bin_status` tool SHALL
   return the bin's fill level, location description, waste type, last collection time and issue
   status from Bin_Records.
2. WHEN `get_bin_status` is called with a bin identifier absent from Bin_Records, THE
   `get_bin_status` tool SHALL return a descriptive error naming the requested identifier.
3. THE `get_bin_status` tool SHALL validate the bin identifier input before reading Bin_Records.

### Requirement 5: assess_collection_priority tool

**User Story:** As a municipal team member, I want the EcoMind_Agent to calculate which bins
need attention first, so that I can prioritise collection.

#### Acceptance Criteria

1. WHEN `assess_collection_priority` is called, THE `assess_collection_priority` tool SHALL
   calculate a numeric priority score for each bin from the bin's fill level and last
   collection time using application code.
2. THE `assess_collection_priority` tool SHALL classify a bin as overflowing when the bin's fill
   level meets or exceeds the overflow threshold.
3. THE `assess_collection_priority` tool SHALL return the bins ordered by descending priority
   score.

### Requirement 6: create_collection_plan tool

**User Story:** As a waste-collection coordinator, I want a recommended collection order, so
that I can dispatch within vehicle capacity.

#### Acceptance Criteria

1. WHEN `create_collection_plan` is called, THE `create_collection_plan` tool SHALL recommend a
   collection order based on priority score and distance estimates from Bin_Records.
2. THE `create_collection_plan` tool SHALL keep the assigned bins within the available vehicle
   capacity.
3. THE `create_collection_plan` tool SHALL label the result as a recommendation rather than a
   completed real-world action.

### Requirement 7: report_bin_issue tool

**User Story:** As a campus administrator, I want to report a damaged bin, so that the bin is
logged for follow-up.

#### Acceptance Criteria

1. WHEN `report_bin_issue` is called with a valid bin identifier and a description, THE
   `report_bin_issue` tool SHALL create a simulated issue report and return its report ID.
2. WHEN `report_bin_issue` is called with a bin identifier absent from Bin_Records, THE
   `report_bin_issue` tool SHALL return a descriptive error.
3. WHEN `report_bin_issue` is called for a bin that already has an open issue with the same
   description, THE `report_bin_issue` tool SHALL return the existing report ID rather than
   creating a duplicate report.

### Requirement 8: Decision record contract

**User Story:** As the project owner, I want every decision recorded in a structured form, so
that the Demo_UI and the benchmark can show what happened.

#### Acceptance Criteria

1. THE EcoMind_Agent SHALL append one Decision_Record to the `decisions` list for each Decider
   call.
2. THE Decision_Record SHALL include a `verdict` field, the selected Policy_Category, the
   category probabilities in the range 0 to 1, the confidence, the latency in `decider_ms`, and
   the action taken.
3. THE `chat()` method SHALL return a dict containing `reply`, `decisions`, `model_id` and
   `latency_ms`.
4. THE EcoMind_Agent constructor SHALL accept an `eager` boolean parameter for demos.

### Requirement 9: Low-confidence, ambiguous and human-review handling

**User Story:** As a municipal team member, I want the EcoMind_Agent to ask when the EcoMind_Agent
is unsure, so that an uncertain request is never treated as a confirmed emergency.

#### Acceptance Criteria

1. WHILE the Decider's confidence in the selected Policy_Category is below 0.7, THE EcoMind_Agent
   SHALL request a clarification question from the user or route the request for human review.
2. IF the Policy_Classifier classifies a request as `urgent_overflow` with confidence below 0.7,
   THEN THE EcoMind_Agent SHALL request clarification or human review rather than acting as a
   confirmed emergency.
3. IF the request lacks an essential piece of information needed by the selected tool, THEN THE
   EcoMind_Agent SHALL ask the user for that information before running the tool.

### Requirement 10: Synthetic data

**User Story:** As a developer, I want realistic sample data, so that the EcoMind_Agent runs
anywhere without live sensors.

#### Acceptance Criteria

1. THE Bin_Records SHALL store simulated bin identifiers, fill levels, location descriptions,
   waste types, last collection times, issue status and available vehicle capacity under
   `agent/data/`.
2. THE Demo_UI SHALL clearly distinguish simulated records from live data.
3. IF no recorded value exists for a sensor reading, traffic condition, dispatch or
   environmental benefit, THEN THE EcoMind_Agent SHALL report the value as unavailable rather
   than inventing the value.

### Requirement 11: Model integration

**User Story:** As the project owner, I want the EcoMind_Agent to use the kit's supported
models, so that the submission meets the hackathon rules.

#### Acceptance Criteria

1. THE EcoMind_Agent SHALL build the generative model with `decider_kit.llm.agent_model()` and
   call the generative model through a Strands `Agent`.
2. THE Policy_Classifier SHALL use the Decider client from `decider_kit` for the policy
   classification.
3. THE deployed EcoMind_Agent SHALL run the generative part on Amazon Bedrock.
4. IF a model is unavailable, THEN THE EcoMind_Agent SHALL report the real error and use an
   explicitly labelled development fallback only where appropriate.

### Requirement 12: Secrets handling

**User Story:** As the project owner, I want no secrets in source code, so that the repository
stays safe.

#### Acceptance Criteria

1. THE EcoMind_Agent SHALL read credentials from the git-ignored `.env` file through
   `decider_kit` configuration.
2. THE project SHALL keep `.env.example` with placeholder values only.
3. IF a development fallback produces a classification, THEN THE EcoMind_Agent SHALL label that
   classification as fallback-produced in the Decision_Record.

### Requirement 13: Demo user experience

**User Story:** As a waste-collection coordinator, I want a clear chat interface with a decision
panel, so that I understand what the EcoMind_Agent decided and why.

#### Acceptance Criteria

1. THE Demo_UI SHALL display an EcoMind AI project heading and a concise introduction.
2. THE Demo_UI SHALL provide a chat interface for submitting waste-management requests.
3. THE Demo_UI SHALL display a decision panel showing the selected Policy_Category and the
   confidence.
4. WHEN a tool returns bin information, THE Demo_UI SHALL display the relevant bin information.
5. WHEN a collection recommendation or an issue report is produced, THE Demo_UI SHALL display
   the recommendation or the report.
6. THE Demo_UI SHALL display an explanation of why the EcoMind_Agent chose the workflow.
7. WHERE a decision needs clarification or human review, THE Demo_UI SHALL show a clear
   indicator.
8. THE Demo_UI SHALL show a history of recent decisions within the demo session.
9. THE Demo_UI SHALL use a professional, responsive, sustainability-themed design with
   accessible controls, clear loading states and understandable errors.

### Requirement 14: Testing and evaluation

**User Story:** As the project owner, I want labelled evaluation cases, so that I can measure
the decision honestly.

#### Acceptance Criteria

1. THE `agent/eval_cases.jsonl` file SHALL contain at least 24 labelled evaluation cases.
2. THE evaluation cases SHALL be divided into a Tune_Split and a separate held-out Test_Split.
3. THE evaluation cases SHALL cover each Policy_Category, ambiguous and borderline requests,
   low-confidence handling, correct tool routing, missing and invalid bin identifiers, overflow
   and collection-priority calculations, vehicle capacity constraints, issue reporting and
   duplicate reports, model failures and unavailable services, and the agent interface and
   decision-record contract.
4. THE project SHALL report actual accuracy, latency, confidence and errors from completed
   benchmark runs.
5. THE project SHALL report actual test results, including any failures, from completed test
   runs.
6. THE project SHALL tune the Policy_Classifier questions only on the Tune_Split.

### Requirement 15: Deployment and completion

**User Story:** As the project owner, I want the project ready to submit, so that the project
passes the hackathon checks.

#### Acceptance Criteria

1. THE EcoMind_Agent SHALL replace the kit's example agent in the `agent/` directory.
2. THE reusable Policy_Classifier SHALL be documented in `agent/decision.py` under a
   `REUSABLE DECISION PATTERN` header.
3. THE project SHALL preserve the kit attribution line "Built with the AWS User Group Madurai
   Strands Decider hackathon kit" in the README, the article footer, the video end card and the
   Demo_UI.
4. THE local demo and the AWS deployment SHALL be verified.
5. THE project SHALL keep the `HackathonAgent.chat()` return contract including `reply` and the
   `decisions` records.
