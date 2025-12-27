#!/usr/bin/env bash
set -e

# Run the pipeline once
docker compose -f compose.yml run --rm app
