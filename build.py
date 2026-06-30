#!/usr/bin/env python3
"""
Build script for the Warshawsky Family Tree site.

Reads:
  family_db.json          — family data (people, vitals, photo filenames)
  buildsystem/template.html — HTML/JS template with __PEOPLE_DATA_JSON__ placeholder
  photos/<id>.jpg         — photo files referenced by filename in family_db.json

Writes:
  index.html              — the final self-contained page (published via GitHub Pages)
"""

import base64
import json
import os
import sys
from datetime import date
from pathlib import Path

PHOTOS_DIR = Path(__file__).parent / "photos"
TEMPLATE = Path(__file__).parent / "buildsystem" / "template.html"
DB = Path(__file__).parent / "family_db.json"
OUTPUT = Path(__file__).parent / "index.html"

MAX_DIM = 640
JPEG_QUALITY = 85


def load_and_encode_photo(filepath: Path, label: str) -> str:
    """Read an image file, resize to MAX_DIM, and return a base64 data URL."""
    if not filepath.exists():
        print(f"ERROR: Photo file not found for {label}: {filepath}", file=sys.stderr)
        sys.exit(1)

    try:
        from PIL import Image
        import io
        img = Image.open(filepath).convert("RGB")
        w, h = img.size
        if w > MAX_DIM or h > MAX_DIM:
            if w >= h:
                new_w, new_h = MAX_DIM, round(h * MAX_DIM / w)
            else:
                new_w, new_h = round(w * MAX_DIM / h), MAX_DIM
            img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except ImportError:
        # Pillow not available — encode as-is without resizing
        with open(filepath, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        ext = filepath.suffix.lower().lstrip(".")
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        return f"data:{mime};base64,{encoded}"


def resolve_photo(value: str, label: str) -> str:
    """
    If value is already a data: URL, return it unchanged.
    If it's a plain filename, load it from photos/ and return a data URL.
    """
    if not value:
        return value
    if value.startswith("data:"):
        return value
    filepath = PHOTOS_DIR / value
    return load_and_encode_photo(filepath, label)


def main():
    if not DB.exists():
        print(f"ERROR: {DB} not found.", file=sys.stderr)
        sys.exit(1)
    if not TEMPLATE.exists():
        print(f"ERROR: {TEMPLATE} not found.", file=sys.stderr)
        sys.exit(1)

    with open(DB) as f:
        people = json.load(f)

    # Resolve any photo filenames → base64 data URLs
    for person in people:
        vitals = person.get("vitals") or {}
        if vitals.get("photo"):
            label = f"{person['id']} (vitals.photo)"
            vitals["photo"] = resolve_photo(vitals["photo"], label)

        partner_vitals = person.get("partnerVitals") or {}
        for idx, pv in partner_vitals.items():
            if pv.get("photo"):
                label = f"{person['id']}__p{idx} (partnerVitals.{idx}.photo)"
                pv["photo"] = resolve_photo(pv["photo"], label)

    with open(TEMPLATE) as f:
        template = f.read()

    # Resolve founders photo for the header
    founders = next((p for p in people if p.get("id") == "founders"), None)
    founders_photo = ""
    if founders and founders.get("vitals", {}).get("photo"):
        founders_photo = resolve_photo(founders["vitals"]["photo"], "founders")

    people_json = json.dumps(people, separators=(",", ":"))

    # Compute stats for the header
    descendants = [p for p in people if p.get("branch") != "Founders"]
    partner_count = sum(len(p.get("partners") or []) for p in descendants)
    total_persons = len(descendants) + partner_count
    build_date = date.today().strftime("%B %-d, %Y")

    output = template.replace("__PEOPLE_DATA_JSON__", people_json)
    output = output.replace("__FOUNDERS_PHOTO__", founders_photo)
    output = output.replace("__BUILD_DATE__", build_date)
    output = output.replace("__TOTAL_PERSONS__", str(total_persons))
    output = output.replace("__DESCENDANT_COUNT__", str(len(descendants)))
    output = output.replace("__PARTNER_COUNT__", str(partner_count))

    if "__PEOPLE_DATA_JSON__" in output:
        print("ERROR: Placeholder was not replaced.", file=sys.stderr)
        sys.exit(1)

    with open(OUTPUT, "w") as f:
        f.write(output)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Build complete: {OUTPUT} ({size_kb:.1f} KB)")
    print(f"  People: {len(people)}")


if __name__ == "__main__":
    main()
