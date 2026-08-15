# Web interface

A static frontend over the generated JSON. No build step, no framework, no backend.

```bash
python3 -m http.server 8173 --directory web
```

Then open <http://localhost:8173>. Any static host works — the whole site is files.
`web/` **is** the site root, in development and in production alike, so a path that
works locally works when deployed.

```
web/
├── index.html
├── .nojekyll           GitHub Pages serves the files as-is
├── assets/app.css      layout and theme
├── assets/app.js       router, timeline, detail panel, map
├── assets/ui.js        interface chrome in ar/en/de (content strings never live here)
├── content/            the generated JSON this page fetches
└── vendor/leaflet/     Leaflet 1.9.4, vendored — no CDN dependency
```

The whole of `web/` is what gets deployed, and nothing outside it is — the build
tools, schemas, translation sources and design deck stay in the repo unpublished.

## How it works

**Routing** is `#/<lang>/<view>[/<id>]` — `#/en/muhammad/61` is a shareable deep link to the
Battle of Badr, and it opens the panel and scrolls the timeline to that point. Hash routing
means no server rewrite rules are needed.

**Loading** is per language, on demand: opening the Arabic prophets page fetches
`prophets.ar.json` and `locations.json` and nothing else. Switching language fetches only the
other file and keeps the entry you were reading open. Each document is cached in memory for
the session.

**Zoom** is view density, not map zoom, and it is the answer to browsing high-level vs detailed:

| Level | Shows |
|---|---|
| Overview | Circles and names only — all 25 prophets, or a whole era, in one screen |
| Timeline | Adds dates and certainty badges (default) |
| Expanded | Adds a two-line excerpt of the message or event |

Because there are only 25 + 108 entries, every level renders from data already in memory —
no round-trip per zoom step. The level persists in `localStorage`; `+` / `−` also work as keys.

**Direction** flips with the language. Every rule is written with logical properties
(`inset-inline-start`, `padding-inline-end`, `margin-block`), so Arabic mirrors the whole
interface — the rail moves to the right, the panel to the left — without a separate stylesheet.

## What the interface is careful about

The content pipeline carries certainty, hedged dates and disputed locations. The UI shows them
rather than flattening them:

- **Certainty badges** on every event: ✓ verified, ≈ approximate, ✓/≈ mixed, or unmarked, plus
  the source's own A/B/C date grade. Where the source assigns no grade, the panel says so
  instead of leaving a confident blank. Event 73's "needs separate study" flag is shown too.
- **The dating caveat** appears under every Gregorian date.
- **Routes** for the 17 events that are journeys. The line is drawn through the waypoints that can be
  located; intermediate stages are small dots, so a 21-stage journey stays readable. The full
  itinerary is listed below the map in the reader's language, numbered in order, with unlocatable
  stages shown outlined and a note explaining why they are not on the map.
- **Direction is readable at a glance.** The two ends of a journey differ by *shape* as well as
  colour — an open ring where it departs, a filled teardrop where it arrives — so they stay
  distinguishable in greyscale and to colour-blind readers. Both are `divIcon`s styled by
  `app.css`, so they need no new image assets and theme with the rest of the interface. A legend
  under the map names both ends in words, because shape and colour alone are not enough.
- **The photograph is the destination.** Where an event is a journey, the panel shows the place it
  ends at rather than where it starts, tagged as the destination, so the picture and the map's end
  marker agree. Non-journey events are unchanged.
- **No map without a place.** Where `locations` is empty — Idris, Nuh, Dhul-Kifl — the panel
  prints the source's own wording and no map. Where the identification is `traditional` or
  `disputed`, a note says the pin is approximate.
- **Qur'an attribution** is displayed on any entry that quotes a verse, naming the published
  edition, as the licence requires.
- **Unreviewed translations** carry a banner in English and German while
  `translation.status` is `machine`.

Content keeps inline `**bold**`. It is rendered by building text nodes and `<strong>` elements —
never `innerHTML`.

## Images and maps

Location photos come from **Wikimedia Commons**, hosted by Wikimedia. Each record stores a direct
`upload.wikimedia.org` thumbnail as the fast path and a `Special:FilePath` URL as the fallback;
the `<img>` swaps to the fallback on error, so a purged thumbnail cache cannot leave a blank
panel. Every credit and licence is displayed and links to the Commons file page.

Maps are **Leaflet with OpenStreetMap tiles**. Leaflet is vendored into `web/vendor/`, so the only
third-party request at runtime is for map tiles, and it is made lazily — the library loads the
first time a detail panel with a map is opened.

## Notes for whoever picks this up

- `index.html` is the only HTML file; the two views share one timeline renderer.
- Adding a language means adding a block to `assets/ui.js`, a `LANGS` entry, and building the
  content files — no other change.
- The event circles carry the sequence number rather than the event name. The prophets' circles
  carry the name, as the design shows, because those are short; event titles are full sentences
  in every language and are unreadable at that size, so they sit beside the circle instead.

