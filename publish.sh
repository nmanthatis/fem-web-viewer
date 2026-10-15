#!/usr/bin/env bash
# Commit everything under site/cases and push -> GitHub Actions redeploys Pages.
# Usage: ./publish.sh ["commit message"]
set -euo pipefail
cd "$(dirname "$0")"
# Cache-bust local JS/CSS references (href="style.css", src="js/viewer.js", import './x.js') so a
# browser never pairs a cached old script with a new page. CDN URLs (http...) are left alone.
STAMP=$(date +%Y%m%d%H%M%S)
sed -i -E "/https?:/!s/\.(js|css)(\?v=[0-9]+)?(['\"])/.\1?v=${STAMP}\3/g" site/*.html site/js/*.js
git add -A site
if git diff --cached --quiet; then echo "nothing new to publish"; exit 0; fi
git commit -m "${1:-update cases}"
git push
echo "pushed; the Pages deploy takes ~1 min. Check: gh run list --limit 1"
