# Massachusetts Trip Planner

## Live Demo

**[Open Massachusetts Trip Planner](https://expenditure-lions-exclusion-quad.trycloudflare.com)**

Open the link in a browser to try the planner. No installation or personal API key is required. Use the form or describe your trip in the chat, then click a recommended place to locate it on the map.

This demonstration uses a temporary Cloudflare Tunnel. It is available only while the host computer, Docker containers and tunnel are running. The URL may change when the tunnel is recreated. If the demo is offline, follow the local setup instructions below.


An individual MIT 1.125 Agentic Engineering project. It builds one-day or multi-day itineraries from a local Massachusetts business dataset, checks constraints, and displays stops on an interactive map. Natural-language requests are translated into structured parameters by Claude; Python selects and checks the itinerary.

## Current capabilities

- Dataset-only recommendations with record links and IDs; no LLM-generated venues.
- City constraints, five interest groups, popularity/rating/distance ranking, and daily spending estimates.
- Up to seven consecutive days and 1–12 stops per day; records are not repeated across days.
- Breakfast/lunch/dinner windows, category matching and one meal of each type per day when feasible and Food is selected.
- Recorded opening-hour, route-time, budget, meal, quality, city, radius and duplicate checks with a rebuild log.
- Bounded route reordering within sightseeing blocks; accepts only feasible improvements in total travel time. Not a global optimum.
- Walking, driving and transit through Google Routes when configured; labelled walking/OSRM fallbacks. Transit fails explicitly without Google routing.
- Google Maps stop markers, clickable cards, per-leg navigation links, and daily travel/wait totals.

## Install and run

Use Python 3.10 or newer. Runtime Python code uses only the standard library. Docker uses Python 3.12. Internet access is needed for geocoding and optional routing/maps/chat.

Place the UCSD Google Local **Massachusetts business metadata** file at `data/raw/meta-Massachusetts.json.gz`. Source: https://mcauleylab.ucsd.edu/public_datasets/gdrive/googlelocal/ . The deployment copy includes the metadata file; the 10-core review text file is not used by the current application. This repository should document and respect the source dataset's terms.

```bash
python3 -m planner.server --data data/raw
```

Open `http://127.0.0.1:8000`. Fill the form without a Claude key. Configure environment variables for optional services:

| Variable | Purpose |
|---|---|
| ANTHROPIC_API_KEY | Server-side Claude chat requests |
| ANTHROPIC_MODEL | Account-supported model ID; current project default is claude-sonnet-5-5 |
| ANTHROPIC_BASE_URL | Optional compatible Anthropic endpoint |
| GOOGLE_MAPS_API_KEY | Backend Google Routes key |
| GOOGLE_MAPS_BROWSER_KEY | Separate Maps JavaScript website-restricted key; exposed to the browser by design |
| HOST / PORT | Listener settings; defaults 127.0.0.1 / 8000 |

See [deployment instructions](DEPLOYMENT.md) for Docker, secret input helpers and the temporary public tunnel.

A legacy CLI is also available; it supports fewer options than the web application:

```bash
python3 -m planner --data data/raw --day Saturday --days 2 --interests food,culture --budget 80 --travel straight
python3 -m unittest discover -s tests -v
python3 scripts/evaluate.py --data data/raw
```

The evaluation uses local distance estimates without paid API calls. It is not a live Google routing or chatbot-baseline benchmark.

## Architecture and authorship

| Module | Responsibility |
|---|---|
| planner/data.py | Load and clean metadata; 87,554 of 92,520 records retained under current rules |
| planner/interests.py | Explicit category mapping, visit lengths and meal compatibility |
| planner/planner.py | Candidate scoring and constraint-aware greedy construction |
| planner/optimizer.py | Bounded feasible route-order improvement |
| planner/checker.py | Recheck itinerary against catalog and request constraints |
| planner/agent.py | Build/check/rebuild orchestration and multi-day duplicate exclusion |
| planner/routing.py | Google Routes, OSRM and labelled fallback estimates |
| planner/server.py | HTTP endpoints, geocoding and Claude parameter extraction |
| web/index.html | Form, chat, cards and Google/Leaflet maps |

This is a deterministic planner/checker architecture with LLM-assisted parameter extraction, not an autonomous LLM that searches and writes the entire itinerary. Custom implementation and debugging were developed with substantial OpenAI Codex assistance. The student is responsible for reviewing, understanding and explaining all submitted code. No third-party algorithm implementation is claimed as original research.

External resources: UCSD McAuley Lab Google Local data; Anthropic Claude API; Google Routes and Maps JavaScript APIs; OpenStreetMap Nominatim and tiles; OSRM demo server; Leaflet 1.9.4 through cdnjs; Python and Docker; Cloudflare Tunnel. Google and Anthropic credentials and billing are user-provided. Links: https://www.anthropic.com/ ; https://developers.google.com/maps/documentation ; https://www.openstreetmap.org/ ; https://project-osrm.org/ ; https://leafletjs.com/ ; https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/ . UCTopic and Personalized Showcases are proposal background references, not algorithms implemented here. pandas was proposed but is not a runtime dependency.

## Evidence and limitations

See [evaluation results](evaluation/results.md) and [requirements audit](REQUIREMENTS_AUDIT.md). Existing tests cover planning/checking, meals, city boundaries by address text, route direction, travel modes, budget, order improvement and parsing. They do not prove live availability, globally optimal routes, or current prices.

- Metadata is a September 2021 snapshot; opening hours, closures and prices are not live verified.
- Prices are explicit assumptions: $ → 12, $$ → 25, $$$ → 50, $$$$ → 90 USD per person; missing price → 15. No current menu, admission, tax, tip, transit or parking charges are included.
- Meals are optional Food stops. Limited stops/budget/hours may omit meals. Visit lengths and meal windows are fixed defaults.
- Multiple days are planned sequentially, each from the same starting point. There is no joint geographic clustering or hotel/continuous-trip model.
- City matching uses address text; search radius is 20 km. Walking stop legs are capped at 45 minutes; the separate final endpoint leg can exceed that cap if the day deadline permits it.
- Review-text taste personalization and user-triggered remaining-day replanning are not implemented.
- Only an offline planner/checker evaluation exists; the proposed plain-chatbot comparison is not completed.
- Python's development HTTP server, in-memory rate limits and temporary tunnel are demonstration infrastructure, not a hardened production service.


## Roadmap

Completed: multi-day dataset-grounded planning, meal windows, city restrictions, Google route/map integration, independent checks, bounded route improvement and English documentation.

Remaining: review-text taste personalization; remaining-day replanning after a closure; a matched plain-chatbot baseline on the 20 evaluation requests; joint multi-day geographic clustering; production hosting and persistent API spending controls. Proposal scope changes are documented in REQUIREMENTS_AUDIT.md.
