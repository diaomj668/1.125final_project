"""Update the running planner's Google key without writing credentials to disk."""
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys

runtime = Path(__file__).resolve().parent
if not (runtime / 'compose.yaml').exists():
    sys.exit('compose.yaml is missing beside this script.')
key = getpass.getpass('Google Routes API Key (hidden): ').strip()
if not key:
    sys.exit('No key entered; nothing changed.')
# Docker inspection stays in memory. Never print the configuration or credentials.
result = subprocess.run(['docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project.working_dir=' + str(runtime), '--filter', 'label=com.docker.compose.service=planner'], capture_output=True, text=True)
if result.returncode:
    sys.exit('Planner container not found. Start the planner first.')
container_id = result.stdout.strip().splitlines()
if not container_id:
    sys.exit('No running planner found for this folder. Start it with Docker Compose first.')
inspection = subprocess.run(['docker', 'inspect', container_id[0]], capture_output=True, text=True, check=True)
config = json.loads(inspection.stdout)[0]
env = os.environ.copy()
for entry in config['Config'].get('Env', []):
    name, _, value = entry.partition('=')
    if name in ('ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL', 'ANTHROPIC_BASE_URL', 'GOOGLE_MAPS_BROWSER_KEY'):
        env[name] = value
env['GOOGLE_MAPS_API_KEY'] = key
if not env.get('ANTHROPIC_API_KEY'):
    sys.exit('The running container has no Claude key; nothing changed.')
subprocess.run(['docker', 'compose', 'up', '-d', '--build', '--no-deps', 'planner'], cwd=runtime, env=env, check=True)
print('Google Key configured. The existing public tunnel was kept running. Return to the planner and refresh the page.')
