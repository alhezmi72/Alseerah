# Alseerah — السيرة

An interactive timeline of the prophets from Adam to Muhammad ﷺ, and of the 108
major events in the Prophet's life, in **Arabic, English and German**.

🌐 **[alhezmi72.github.io/Alseerah](https://alhezmi72.github.io/Alseerah/)**

A static site: no backend, no framework, no build step to run it. Content is
generated from Arabic markdown into per-language JSON that the page fetches on
demand.

---

## What it does

- **Two timelines.** 25 prophets on the landing page; 108 events across six eras
  on the Prophet's page, each rendered as the incremental circle-and-arrow
  sequence from the original design.
- **Three zoom levels** — Overview, Timeline, Expanded — for browsing at a high
  level or in detail. All three render from data already in memory.
- **Three languages**, switchable without losing your place. Arabic mirrors the
  whole interface to right-to-left; the layout uses logical properties, so there
  is no second stylesheet.
- **Maps** via OpenStreetMap, including drawn routes for the four journey events —
  the Hijrah's 21 stages, Tabuk, the pilgrimage, and Usamah's expedition.
- **Photographs** of the locations, from Wikimedia Commons under free licences.

## What makes it a reference rather than a storybook

The source document grades its own reports, and the pipeline carries that all the
way to the screen instead of flattening it:

- Every event shows the source's own ✓ verified / ≈ approximate mark, and its
  A/B/C date grade where one was assigned. Where the source assigned none, the
  panel says so rather than leaving a confident blank.
- Dates keep their hedges — *نحو*, *تقريبًا*, *على المشهور* — and every Gregorian
  date carries the source's warning about converting from a lunar calendar.
- Places are marked established, traditional or disputed. Where the source
  declines to locate something, no map is drawn. Route stages that cannot be
  fixed at all are listed but never pinned.
- Qur'anic verses are never freshly translated: each quotation reproduces a
  published edition, with attribution shown.

## Layout

```
web/                the published site — everything here, and only this, is deployed
  index.html
  assets/           app.js, app.css, ui.js
  vendor/leaflet/   vendored, so the site has no runtime CDN dependency
  content/          generated JSON + the location and route registries

prophets-content            ┐ Arabic source of record, authored by hand
Mohammed-historical-events  ┘
i18n/               English and German strings, and the Qur'an edition registry
schema/             JSON Schema for every content file
tools/              build, validate, attribution
features            the original feature requirements
design.pptx         the original design
```

`web/content/*.json` is **generated**. Never edit it by hand — edit the markdown
or `i18n/`, then rebuild. CI rebuilds on every push and fails if the committed
output has drifted, so the rule is enforced rather than merely documented.

## Working on it

```bash
python3 -m http.server 8173 --directory web
```

Then open <http://localhost:8173> — the same layout the published site uses.

```bash
python3 tools/build_content.py        # markdown + i18n -> web/content/*.json
python3 tools/make_attribution.py     # regenerate ATTRIBUTION.md from the data
```

```bash
python3 -m venv .venv && .venv/bin/pip install jsonschema && .venv/bin/python tools/validate_content.py
```

More detail in [web/README.md](web/README.md) (the interface) and
[web/content/README.md](web/content/README.md) (the content pipeline, and the
open items).

## Licence

| | |
|---|---|
| Code | [MIT](LICENSE) |
| Content | [CC BY-SA 4.0](LICENSE-CONTENT) |
| Photographs, Qur'an translations, map data | Their own terms — see [ATTRIBUTION.md](ATTRIBUTION.md) |

## Status

The Arabic is the source of record and is complete. **The English and German
translations are machine-produced and have not yet been reviewed by a human** —
every generated file records this in `translation.status`, and the interface
shows a banner. Reviewers should work in `i18n/`, never in `web/content/`.
