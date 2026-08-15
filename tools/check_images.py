#!/usr/bin/env python3
"""Check that every Wikimedia image is still present and still freely licensed.

    python3 tools/check_images.py

Asks the Commons API about all files in ONE request (it accepts up to 50 titles),
rather than issuing a HEAD per image — which gets rate-limited from shared CI
addresses and is unfriendly to Wikimedia either way.

Exit codes:
    0  every image is present and free (thumbnail drift is only a warning)
    1  a file is missing, or its licence is no longer free — the site would
       either show a gap or breach the licence, so this must block a deploy
    0  the API could not be reached; reported as inconclusive, never a failure,
       because a network blip is not a content problem
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCATIONS = ROOT / "web" / "content" / "locations.json"
API = "https://commons.wikimedia.org/w/api.php"
BATCH = 50

# Mirrors the allow-list the fetch script applies when an image is first chosen.
FREE = re.compile(r"^(cc0|cc[ -]by|public domain|pd[- ])", re.I)

UA = ("AlseerahImageCheck/1.0 (https://github.com/alhezmi72/Alseerah; "
      "static educational timeline)")


def api(titles):
    query = urllib.parse.urlencode({
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "titles": "|".join(f"File:{t}" for t in titles),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "1200",
    })
    request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def strip_html(value):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", value or "")).strip()


def main() -> int:
    locations = json.loads(LOCATIONS.read_text(encoding="utf-8"))["locations"]
    images = {l["image"]["file"]: l for l in locations if l["image"]}
    if not images:
        print("no images to check")
        return 0

    pages = []
    files = list(images)
    try:
        for start in range(0, len(files), BATCH):
            pages += api(files[start:start + BATCH]).get("query", {}).get("pages", [])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
        print(f"::warning::Could not reach the Commons API ({err}). "
              f"Image check skipped — this is not treated as a failure.")
        return 0

    missing, unfree, moved = [], [], []
    seen = set()

    for page in pages:
        name = page["title"].removeprefix("File:")
        # The API normalises underscores and spaces; match back to our record.
        record = images.get(name) or images.get(name.replace("_", " "))
        if record is None:
            continue
        seen.add(record["image"]["file"])

        if page.get("missing"):
            missing.append(record["id"])
            continue

        info = page["imageinfo"][0]
        licence = strip_html(info.get("extmetadata", {}).get("LicenseShortName", {}).get("value"))
        if not FREE.match(licence or ""):
            unfree.append((record["id"], licence or "unknown"))
        # A re-upload changes the thumbnail path. The page falls back to
        # Special:FilePath, so this is a nudge to refresh, not a failure.
        if info.get("thumburl", "").split("?")[0] != record["image"]["thumbUrl"]:
            moved.append(record["id"])

    for name, record in images.items():
        if name not in seen:
            missing.append(record["id"])

    print(f"{len(images) - len(missing) - len(unfree)}/{len(images)} images present and free")

    for lid in sorted(set(missing)):
        print(f"::error::{lid}: file no longer on Commons — {images_by_id(images, lid)}")
    for lid, licence in unfree:
        print(f"::error::{lid}: licence is now {licence!r}, which is not on the free allow-list")
    for lid in sorted(set(moved)):
        print(f"::warning::{lid}: thumbnail URL has moved (the page falls back to "
              f"Special:FilePath). Re-run the image fetch to refresh it.")

    return 1 if missing or unfree else 0


def images_by_id(images, lid):
    return next((f for f, r in images.items() if r["id"] == lid), "?")


if __name__ == "__main__":
    raise SystemExit(main())
