#!/bin/bash
# Build the site and apply password protection, then commit and push.
# Usage: ./build_and_encrypt.sh
set -e

cd "$(dirname "$0")"

# Read password from local file (never hardcode it here)
if [ ! -f .wfc_password ]; then
  echo "ERROR: .wfc_password file not found. Create it with the family password on one line."
  exit 1
fi
WFC_PASSWORD=$(tr -d '[:space:]' < .wfc_password)

echo "=== Building site ==="
python3 build.py

echo ""
echo "=== Encrypting ==="
python3 encrypt.py --password "$WFC_PASSWORD"
python3 encrypt.py --password "$WFC_PASSWORD" \
  --input data-viz/index.html \
  --title "Warshawsky Family — Data Visualizations" \
  --url "https://warshawskyfamily.com/data-viz/"

echo ""
echo "=== Committing ==="
git add index.html data-viz/index.html
git commit -m "Rebuild and re-encrypt site"

echo ""
echo "=== Pushing to GitHub Pages ==="
git push
echo ""
echo "Done. Site is live at warshawskyfamily.com"
