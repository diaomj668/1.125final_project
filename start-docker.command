#!/bin/bash
set -e
cd "$(dirname "$0")"
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  read -r -s -p "Anthropic API Key (optional, Enter to skip): " ANTHROPIC_API_KEY
  printf '\n'
  export ANTHROPIC_API_KEY
fi
if [ -z "${GOOGLE_MAPS_API_KEY:-}" ]; then
  read -r -s -p "Google Routes API Key (optional, Enter to skip): " GOOGLE_MAPS_API_KEY
  printf '\n'
  export GOOGLE_MAPS_API_KEY
fi
if [ -z "${GOOGLE_MAPS_BROWSER_KEY:-}" ]; then
  read -r -s -p "Google Maps website-restricted Key (optional, Enter to skip): " GOOGLE_MAPS_BROWSER_KEY
  printf '\n'
  export GOOGLE_MAPS_BROWSER_KEY
fi
docker compose --profile share up -d --build
printf '\nLocal website: http://localhost:8000\nPublic link appears below (https://...trycloudflare.com):\n'
docker compose logs -f tunnel
