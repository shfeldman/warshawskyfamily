#!/bin/bash
# Build the site and apply password protection, then commit and push.
# Usage: ./build_and_encrypt.sh
set -e

cd "$(dirname "$0")"

echo "=== Building site ==="
python3 build.py

echo ""
echo "=== Encrypting ==="
python3 encrypt.py --password LouisRoseWarshawsky

echo ""
echo "=== Committing ==="
git add index.html
git commit -m "Rebuild and re-encrypt site"

echo ""
echo "=== Pushing to GitHub Pages ==="
git push
echo ""
echo "Done. Site is live at warshawskyfamily.com"
