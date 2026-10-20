# EcoMind AI — Benchmark Results

## Status

The local Strands Decider server (`./kit serve`) was not running during automated execution.
Benchmark tasks 10.1–10.3 require a live Decider connection and must be run manually.

## How to run

```bash
# 1. Start the local Decider (or set DECIDER_API_KEY for the hosted API)
./kit serve

# 2. Tune split (14 cases) — use results to refine CATEGORY_QUESTION descriptions
./kit bench --split tune

# 3. Test split (10 held-out cases) — run after tuning is complete
./kit bench --split test
```

## Eval cases summary

| File | Total | Tune | Test |
|---|---|---|---|
| `agent/eval_cases.jsonl` | 24 | 14 | 10 |

| Category | Tune | Test |
|---|---|---|
| urgent_overflow | 3 + 2 borderline = 5 | 2 + 1 ambiguous = 3 |
| routine_collection | 3 + 1 borderline = 4 | 2 |
| bin_issue | 3 | 2 + 1 tricky = 3 |
| general_information | 2 + 1 low-info = 3 | 2 |

## Results placeholder

Results will be filled in after `./kit bench` runs with a live Decider connection.

| Metric | Tune split | Test split |
|---|---|---|
| Accuracy | — | — |
| Mean confidence | — | — |
| Mean decider_ms | — | — |
| Errors | — | — |

*Note: Results above are placeholders. Run `./kit bench` and paste actual output here.*