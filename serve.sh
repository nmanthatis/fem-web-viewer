#!/usr/bin/env bash
# Preview the site locally at http://localhost:8000
cd "$(dirname "$0")/site" && python3 -m http.server 8000
