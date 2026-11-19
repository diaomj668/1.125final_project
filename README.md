# Massachusetts Trip Planner (1.125 term project, midpoint version)

A one-day itinerary planner for Massachusetts. You choose a day, interests and a budget. The planner
picks places from real business records, and an independent checker verifies every stop against
its record. If a check fails, the plan is rebuilt without that place.

**Status (midpoint):** version 1 is working: one-day itineraries with hours, travel-time and
budget checks, plus a 20-request evaluation. Not done yet: taste ranking, multi-day plans,
re-planning when a stop closes, and LLM-written plan text. See [Roadmap](#roadmap).

## How it works

```
 request (day, interests, budget, hours)
        │
        ▼
 planner/planner.py   greedy search over places that are open for the whole visit
        │
        ▼
 planner/checker.py   re-checks every stop against the raw record (hours, travel, budget, links)
        │
   pass ├──► plan with per-stop record links
   fail └──► planner/agent.py excludes the failing place and rebuilds (up to 5 attempts)
```

| File | Role |
|---|---|
| `planner/data.py` | Loads `meta-Massachusetts.json.gz`, drops permanently closed, out-of-state and bad-coordinate records |
| `planner/hours.py` | Parses hours text such as `5:30AM–1PM`, `Closed`, `Open 24 hours`; finds the earliest visit start |
| `planner/geo.py` | Haversine distance × 1.3 detour factor at 25 km/h to estimate travel time |
| `planner/interests.py` | Maps interests (food, culture, outdoors, shopping, nightlife) to Google category names |
| `planner/planner.py` | Builds the itinerary; spreads stops across interests; keeps cost under budget |
| `planner/checker.py` | Independent verification; returns a list of rule violations |
| `planner/agent.py` | Plan → check → rebuild loop, with a log of every attempt |
| `planner/cli.py` | Command-line interface |
| `scripts/evaluate.py` | Runs 20 fixed requests and writes `evaluation/results.md` |
| `tests/test_planner.py` | Unit tests for hours parsing, planning and checking |

### Checker rules

`record_exists`, `traceability` (the stop's link matches the record), `duplicate`, `hours_unknown`,
`open_hours` (the whole visit fits inside the recorded hours for the trip day), `within_day`,
`duration`, `travel_time`, `budget`.

### Design choices

- **Places with no recorded hours for the trip day are never planned.** Without hours we cannot
  verify a stop, so we do not guess.
- **Prices are estimates.** Price tiers map to fixed USD values (`$`=12, `$$`=25, `$$$`=50, `$$$$`=90).
  Places with no price get a default of $15. The output labels which estimate was used. Only about
  20% of records have a price.
- **Travel time is an estimate.** It is straight-line distance × 1.3 at 25 km/h, not a routing API.
- **Quality filter:** rating ≥ 4.0 and at least 5 reviews, so the planner does not pick
  low-information places.
- **Data age:** the snapshot is from September 2021, so some places may have closed since.

## Data

Source: the Google Local dataset from the UCSD McAuley lab (Massachusetts business metadata file).
Put the file here (not included in the repository because of its size):

```
data/raw/meta-Massachusetts.json.gz
```

The reviews file (`review-Massachusetts_10.json.gz`) is not used in version 1. It is planned for
taste ranking.

Dataset citations: the Google Local data is from the McAuley lab (UCSD). Related work cited in the
proposal: UCTopic (ACL 2022) and Personalized Showcases (SIGIR 2023).

Data cleaning on the 92,520 records:

| Step | Removed |
|---|---|
| Permanently closed (`state` field) | 4,925 |
| Address names a state other than Massachusetts | 31 |
| Coordinates outside Massachusetts (placeholder or bad geocodes) | 10 |
| **Kept** | **87,554** |

The proposal reported 87,588 after removing 7 out-of-state records. The rules here are stricter,
so the count is slightly lower.

## Install and run

Requirements: Python 3.10 or newer. No third-party packages are needed.

```bash
cd 1.125final_project
python -m planner --data data/raw --day Saturday --interests food,culture --budget 80
```

Options: `--day`, `--interests` (comma list), `--budget` (USD per person), `--start` and `--end`
(24-hour HH:MM), `--max-stops`, `--anchor lat,lon` (default: Boston Common), `--radius-km`,
`--json plan.json`.

### Web page

`web/index.html` is a single file you can open in a browser. It contains the same planning and
checking rules in JavaScript, plus the Boston-area place data (5,754 places, 2.3 MB), so it needs
no server. The map uses Leaflet (cdnjs) and OpenStreetMap tiles, so it needs an internet connection; the plan itself works offline. Open it directly, or serve the folder with `python -m http.server` and visit
`http://127.0.0.1:8000`. The page covers Boston and a 20 km radius only. To rebuild it after changing
the data or rules:

```bash
python scripts/export_web_data.py --data data/raw
```

This writes `web/index.html` from `web/index.template.html`. Check the JavaScript against the Python
planner after any rule change: for the same request, both should give the same stops and times.

Tests and evaluation:

```bash
python -m unittest discover -s tests -v
python scripts/evaluate.py --data data/raw
```

## Evaluation (midpoint)

Results are in [`evaluation/results.md`](evaluation/results.md). Summary on the 20 fixed requests:

- 20 of 20 requests produced a checked one-day plan.
- 0 time clashes, 0 hours/record violations, 0 over-budget plans.
- No plan needed a rebuild, because the planner only uses places that are open for the whole visit.

Caveat: this result is partly by construction. The planner already filters for hours and budget, so
the checker rarely fails here. The unit tests check that the checker does catch bad plans (for
example a visit outside opening hours, an unknown place, or an over-budget plan).

Not yet done: the proposal planned a comparison with a plain chatbot on the same 20 requests. That
needs an LLM API key and is planned for the final version.

## Roadmap

- **Final:** taste ranking using review text, multi-day plans (hours checked for each day),
  re-planning when a stop closes, LLM-drafted plan text (the proposal's "Agent" step), and the
  chatbot baseline comparison.
- **Out of scope:** booking, payment and live availability.

## External resources

- Google Local business metadata, UCSD McAuley lab (Massachusetts file). Used for places, categories,
  hours, prices and ratings.
- Python standard library only (`gzip`, `json`, `dataclasses`, `math`, `argparse`, `unittest`).
