#!/usr/bin/env python3
"""
One-time migration: extract base64 photo data from family_db.json into files in photos/.

Run once. After this, family_db.json will only hold filenames like "henry.jpg",
and the actual images will live in photos/.
"""

import base64
import json
import os
from pathlib import Path

DB = Path(__file__).parent / "family_db.json"
PHOTOS_DIR = Path(__file__).parent / "photos"
PHOTOS_DIR.mkdir(exist_ok=True)

with open(DB) as f:
    people = json.load(f)

migrated = 0

for person in people:
    pid = person["id"]

    vitals = person.get("vitals") or {}
    photo = vitals.get("photo", "")
    if photo and photo.startswith("data:"):
        header, data = photo.split(",", 1)
        ext = "jpg"
        filename = f"{pid}.{ext}"
        filepath = PHOTOS_DIR / filename
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(data))
        vitals["photo"] = filename
        print(f"  Migrated {pid} photo → photos/{filename}")
        migrated += 1

    partner_vitals = person.get("partnerVitals") or {}
    for idx, pv in partner_vitals.items():
        photo = pv.get("photo", "")
        if photo and photo.startswith("data:"):
            header, data = photo.split(",", 1)
            ext = "jpg"
            filename = f"{pid}__p{idx}.{ext}"
            filepath = PHOTOS_DIR / filename
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(data))
            pv["photo"] = filename
            print(f"  Migrated {pid}__p{idx} photo → photos/{filename}")
            migrated += 1

with open(DB, "w") as f:
    json.dump(people, f, indent=2)

if migrated:
    print(f"\nMigrated {migrated} photo(s). family_db.json updated.")
else:
    print("No base64 photos found in family_db.json — nothing to migrate.")
