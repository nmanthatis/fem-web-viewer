#!/usr/bin/env bash
# Commit everything under site/cases and push -> GitHub Actions redeploys Pages.
# Usage: ./publish.sh ["commit message"]
set -euo pipefail
cd "$(dirname "$0")"
git add -A site
if git diff --cached --quiet; then echo "nothing new to publish"; exit 0; fi
git commit -m "${1:-update cases}"
git push
echo "pushed; the Pages deploy takes ~1 min. Check: gh run list --limit 1"
