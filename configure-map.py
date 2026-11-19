"""Update the running planner's Google key without writing credentials to disk."""
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys

runtime = Path('/private/tmp/mit125-trip-planner')
if not (runtime / 'compose.yaml').exists():
    sys.exit('Runtime folder missing. Ask Codex to restore the deployment folder.')
key = getpass.getpass('Google Maps JavaScript website-restricted Key (hidden): ').strip()
if not key:
    sys.exit('No key entered; nothing changed.')
# Docker inspection stays in memory. Never print the configuration or credentials.
result = subprocess.run(['docker', 'inspect', 'mit125-trip-planner-planner-1'], capture_output=True, text=True)
if result.returncode:
    sys.exit('Planner container not found. Start the planner first.')
config = json.loads(result.stdout)[0]
env = os.environ.copy()
for entry in config['Config'].get('Env', []):
    name, _, value = entry.partition('=')
    if name in ('ANTHROPIC_API_KEY', 'ANTHROPIC_MODEL', 'ANTHROPIC_BASE_URL', 'GOOGLE_MAPS_API_KEY'):
        env[name] = value
env['GOOGLE_MAPS_BROWSER_KEY'] = key
if not env.get('ANTHROPIC_API_KEY'):
    sys.exit('The running container has no Claude key; nothing changed.')
subprocess.run(['docker', 'compose', 'up', '-d', '--build', '--no-deps', 'planner'], cwd=runtime, env=env, check=True)
print('Google map display key configured. The existing public tunnel was kept running. Tell Codex: Google configured.')
