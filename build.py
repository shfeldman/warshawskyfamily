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
import time
import urllib.request
import urllib.parse
from datetime import date
from pathlib import Path

PHOTOS_DIR = Path(__file__).parent / "photos"
TEMPLATE = Path(__file__).parent / "buildsystem" / "template.html"
DB = Path(__file__).parent / "family_db.json"
REUNION_DB = Path(__file__).parent / "reunion_db.json"
OUTPUT = Path(__file__).parent / "index.html"
LOCATIONS_CACHE = Path(__file__).parent / "locations_cache.json"

REUNION_MAX_DIM = 320
REUNION_JPEG_QUALITY = 38

MAX_DIM = 500
JPEG_QUALITY = 78


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


def geocode_location(location: str):
    """Geocode a 'City, State' string via Nominatim. Returns [lat, lng] or None."""
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({
        "q": location, "format": "json", "limit": 1
    })
    req = urllib.request.Request(url, headers={"User-Agent": "warshawskyfamily-build/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read())
        if results:
            return [round(float(results[0]["lat"]), 4), round(float(results[0]["lon"]), 4)]
    except Exception as e:
        print(f"  WARNING: geocoding failed for '{location}': {e}", file=sys.stderr)
    return None


def resolve_location_coords(people: list) -> dict:
    """Return {location: [lat, lng]} for all people with vitals.location."""
    cache = {}
    if LOCATIONS_CACHE.exists():
        with open(LOCATIONS_CACHE) as f:
            cache = json.load(f)

    locations = {p["vitals"]["location"] for p in people
                 if p.get("vitals", {}).get("location")}
    new_found = False
    for loc in sorted(locations):
        if loc not in cache:
            print(f"  Geocoding: {loc} ...", end=" ", flush=True)
            coords = geocode_location(loc)
            if coords:
                cache[loc] = coords
                new_found = True
                print(coords)
            else:
                print("not found")
            time.sleep(1)  # Nominatim rate limit: 1 req/sec

    if new_found:
        with open(LOCATIONS_CACHE, "w") as f:
            json.dump(cache, f, indent=2, sort_keys=True)
        print(f"  Location cache updated: {LOCATIONS_CACHE.name}")

    return {loc: cache[loc] for loc in locations if loc in cache}


def load_and_encode_reunion_photo(filepath: Path, label: str) -> str:
    """Read a reunion photo, resize to REUNION_MAX_DIM, return base64 data URL."""
    if not filepath.exists():
        print(f"WARNING: Reunion photo not found: {filepath}", file=sys.stderr)
        return ""
    try:
        from PIL import Image
        import io
        img = Image.open(filepath).convert("RGB")
        w, h = img.size
        if w > REUNION_MAX_DIM or h > REUNION_MAX_DIM:
            if w >= h:
                new_w, new_h = REUNION_MAX_DIM, round(h * REUNION_MAX_DIM / w)
            else:
                new_w, new_h = round(w * REUNION_MAX_DIM / h), REUNION_MAX_DIM
            img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=REUNION_JPEG_QUALITY)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except ImportError:
        with open(filepath, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"


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

    # Load and encode reunion photos
    reunion_photos = []
    if REUNION_DB.exists():
        with open(REUNION_DB) as f:
            reunion_raw = json.load(f)
        for entry in reunion_raw:
            encoded = load_and_encode_reunion_photo(PHOTOS_DIR / entry["photo"], f"reunion {entry['year']}")
            if encoded:
                reunion_photos.append({"year": entry["year"], "photo": encoded})

    people_json = json.dumps(people, separators=(",", ":"))
    reunion_photos_json = json.dumps(reunion_photos, separators=(",", ":"))
    location_coords = resolve_location_coords(people)
    location_coords_json = json.dumps(location_coords, separators=(",", ":"))

    # Compute stats for the header
    descendants = [p for p in people if p.get("branch") != "Founders"]
    partner_count = sum(len(p.get("partners") or []) for p in descendants)
    total_persons = len(descendants) + partner_count
    build_date = date.today().strftime("%B %-d, %Y")

    output = template.replace("__PEOPLE_DATA_JSON__", people_json)
    output = output.replace("__REUNION_PHOTOS_JSON__", reunion_photos_json)
    output = output.replace("__LOCATION_COORDS_JSON__", location_coords_json)
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
