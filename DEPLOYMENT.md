# Docker deployment

Requirements: Docker Desktop and Python 3.10+ for the credential configuration helpers.

1. Put `meta-Massachusetts.json.gz` in `data/raw/`.
2. Run `bash start-docker.command`. Enter the Anthropic key at the hidden prompt. Optionally enter a Google Routes key.
3. Open `http://localhost:8000`. The tunnel log prints a temporary public `trycloudflare.com` URL.
4. Configure the separate website-restricted Maps JavaScript key using `python3 configure-map.py` after the planner is running. Run the helper from the same checkout used to launch Docker Compose; it discovers that checkout's running planner container.

The backend Routes key must allow Routes API. The map display key must allow Maps JavaScript API and restrict websites to your exact public hostname and `http://localhost:8000/*`. The browser display key is intentionally public; never expose the Routes or Anthropic keys.

`configure-google.py` updates the Routes key while preserving the map key. `configure-map.py` preserves the Routes and Anthropic keys. Neither helper intentionally saves keys to files; Docker administrators can inspect container environment variables.

Stop both services with `docker compose --profile share down` from the deployment directory, No API keys are required to stop the services. Alternatively use Docker Desktop to stop the two project containers. The public link changes when the tunnel is recreated. The computer and Docker must stay running. Temporary files can be removed by the operating system.

For a portable manual launch, set the three environment variables (`ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY`, `GOOGLE_MAPS_BROWSER_KEY`) securely in your shell and run `docker compose --profile share up -d --build`. Do not put real credentials into source code, Git, screenshots, or a Docker image.

Limits: 50 chat calls per UTC day and 10 chat calls per IP per hour in Compose. Counters reset on restart. Routes calls have no persistent global daily budget. Use a fixed production host, a production HTTP server, request limits and persistent spending controls before broad public use.
