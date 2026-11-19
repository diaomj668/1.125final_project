# Evaluation: 20 sample requests (planner with checker)

Data: 87554 businesses after removing 4925 permanently closed, 31 out-of-state and 10 with bad coordinates.

- Requests with a checked plan: 20 / 20
- Plans that needed a rebuild: 0
- Time clashes in final plans (target 0): 0
- Hours/record violations in final plans (target 0): 0
- Plans over budget (target 0): 0

| # | Day | Interests | Budget | Plan? | Stops | Attempts | Clashes | Hours issues | Est. cost |
|---|-----|-----------|--------|-------|-------|----------|---------|--------------|-----------|
| 1 | Monday | food | $40 | yes | 3 | 1 | 0 | 0 | $39 |
| 2 | Tuesday | culture | $60 | yes | 4 | 1 | 0 | 0 | $60 |
| 3 | Wednesday | outdoors | $80 | yes | 4 | 1 | 0 | 0 | $60 |
| 4 | Thursday | shopping | $100 | yes | 4 | 1 | 0 | 0 | $60 |
| 5 | Friday | nightlife | $40 | yes | 2 | 1 | 0 | 0 | $40 |
| 6 | Saturday | food, culture | $60 | yes | 3 | 1 | 0 | 0 | $55 |
| 7 | Sunday | food, outdoors | $80 | yes | 4 | 1 | 0 | 0 | $60 |
| 8 | Monday | culture, outdoors | $100 | yes | 4 | 1 | 0 | 0 | $60 |
| 9 | Tuesday | food, shopping | $40 | yes | 3 | 1 | 0 | 0 | $39 |
| 10 | Wednesday | food, nightlife | $60 | yes | 3 | 1 | 0 | 0 | $52 |
| 11 | Thursday | food | $80 | yes | 4 | 1 | 0 | 0 | $64 |
| 12 | Friday | culture | $100 | yes | 4 | 1 | 0 | 0 | $57 |
| 13 | Saturday | outdoors | $40 | yes | 2 | 1 | 0 | 0 | $30 |
| 14 | Sunday | shopping | $60 | yes | 4 | 1 | 0 | 0 | $57 |
| 15 | Monday | nightlife | $80 | yes | 2 | 1 | 0 | 0 | $75 |
| 16 | Tuesday | food, culture | $100 | yes | 4 | 1 | 0 | 0 | $57 |
| 17 | Wednesday | food, outdoors | $40 | yes | 2 | 1 | 0 | 0 | $40 |
| 18 | Thursday | culture, outdoors | $60 | yes | 4 | 1 | 0 | 0 | $60 |
| 19 | Friday | food, shopping | $80 | yes | 4 | 1 | 0 | 0 | $80 |
| 20 | Saturday | food, nightlife | $100 | yes | 4 | 1 | 0 | 0 | $90 |

Not yet done: a plain-chatbot baseline on the same 20 requests (needs an LLM API key).
