# Container for the planner web server. Build from the project folder:
#   1. copy data/raw/meta-Massachusetts.json.gz into this folder's data/raw/ (not committed to git)
#   2. docker build -t trip-planner .
#   3. docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... trip-planner
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000
COPY planner ./planner
COPY web ./web
COPY data/raw/meta-Massachusetts.json.gz ./data/raw/
EXPOSE 8000
CMD ["python", "-m", "planner.server", "--data", "data/raw"]
