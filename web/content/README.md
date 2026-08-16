# Content pipeline

Arabic markdown is the source of record. The JSON the frontend fetches is generated from it.

```
prophets-content ─┐                          ┌─ content/prophets.{ar,en,de}.json
                  ├── tools/build_content.py ─┤
Mohammed-…events ─┘         ▲                └─ content/muhammad.{ar,en,de}.json
                            │
       i18n/{prophets,events,common,quran}.json   translated strings
       content/locations.json                     language-neutral geo registry
```

**Never hand-edit anything in `content/`.** Arabic comes from the markdown; English and
German come from `i18n/`. Edit the source, rebuild, or they drift apart.

```bash
python3 tools/build_content.py
```

```bash
python3 -m venv .venv && .venv/bin/pip install jsonschema && .venv/bin/python tools/validate_content.py
```

## Files

| File | Contents |
|---|---|
| `locations.json` | 56 places: coordinates, map zoom, names in ar/en/de, and how much the pin can be trusted. Loaded once, reused by all languages. |
| `routes.json` | Journeys as ordered waypoint lists, for the four events that are journeys. Language-neutral — the itinerary is rendered from each waypoint's own name. |
| `prophets.{ar,en,de}.json` | 25 prophets, Adam → Muhammad. ~21 KB each. |
| `muhammad.{ar,en,de}.json` | 108 events in 6 eras. ~80 KB each. |
| `../i18n/*.json` | The translation source. `common.json` holds strings that repeat (dates, places, eras); `prophets.json` and `events.json` hold per-entry text; `quran.json` holds the published verse renderings. |
| `../schema/*.schema.json` | JSON Schema 2020-12 for each. Field descriptions carry the editorial rules. |

Per-language files are fetched independently, so a visitor loads one language's content, not three.
Structure is generated once and shared, so ids and ordering cannot diverge between languages;
`validate_content.py` proves it on every run.

## Design decisions worth knowing

**Verbatim Arabic, derived metadata.** Every Arabic string is copied from the markdown unchanged.
Everything added — ids, slugs, location refs, sort years, categories — is derived, and comes either
from a mechanical rule or from an explicitly reviewable table at the top of `build_content.py`.
Nothing was rewritten, re-dated, or summarised.

**Certainty is a field, not a footnote.** The source grades its own rows and the JSON carries that
through:

- `authenticity.mark` — from the row's own ✓ / ≈ / ✓≈ marker. Currently 84 verified, 19 approximate,
  3 mixed, 2 unmarked.
- `authenticity.qualifier` — the scope the row attaches to its marker, e.g. event 7's
  *"من حيث أصل الرواية"*: verified as to the origin of the report, not every detail.
- `authenticity.grade` — A/B/C date certainty, set **only** for the 11 events the source names
  explicitly in its A/B/C section. `null` means the source did not grade it, never "graded and fine".
- `authenticity.needsSeparateStudy` — set on event 73 (بنو قريظة), where the source itself says the
  details require separate study.

The UI should render these, not hide them. It is what separates this from a storybook.

**Dates stay as written.** `date.hijri` and `date.gregorian` keep their hedges — *نحو*, *تقريبًا*,
*على المشهور*. The hedge is part of the claim. `sortYearHijri` / `sortYearGregorian` are derived
integers for timeline spacing only (negative = before the Hijra) and must never be displayed as
dates. `dateCaveat` at the top of `muhammad.ar.json` is the source's own warning about
Hijri→Gregorian conversion, and belongs anywhere Gregorian dates appear.

**Journeys are routes, not two pins.** Twenty-three events carry a `routeId` into `routes.json` —
event 51 (the Hijrah, 21 stages) and 100 (the farewell rites, 4 stages) are multi-stage; the rest
are two-point journeys. A route states the **direction of travel**, which the source's place column
often does not: `مكة واليمن` for the Year of the Elephant says *Mecca and Yemen*, not that Abrahah's
army marched from Sana'a to Mecca. A route is drawn *in addition to* the event's `locations`, which stay exactly as the
source's place column gave them — the route layer never overwrites the source. Waypoints carry
`precision: "unlocated"` when the place is attested but its position cannot be fixed: nine of the
Hijrah's stages are in that state, so they appear in the written itinerary and leave a gap in the
drawn line rather than getting a guessed pin. The build refuses a route with fewer than two
locatable waypoints, and cross-checks that each route and its event point at each other.

**Where the place column maps to the wrong pin, the resolution is overridden — the text is not.**
`LOCATION_OVERRIDES` in `build_content.py` replaces the ids an event resolves to. Event 38's cell
reads only `مكة`, but the event is the Negus's protection of the migrants, which happened in
Abyssinia; Mecca is where the pressure came from, not where it took place. `placeText` is never
altered, so the panel still prints the Arabic cell verbatim and the override changes only what is
pinned and photographed. Every entry carries its reason, because this is the one place the map
departs from the source column.

**Where the source declines to locate something, so does the JSON.** `placeText` is always shown;
`locations` may be empty (Idris, Nuh, Dhul-Kifl), in which case render no map rather than a guess.
`locationCertainty` distinguishes *quranic* / *traditional* / *unspecified*, and each location's own
`certainty` distinguishes *established* / *traditional* / *disputed* — Al-Ahqaf and the cities of Lot
are marked disputed, and the UI should say so rather than dropping a confident pin.

**Qur'anic verses use a published translation, never a fresh one.** A verse never appears as
translatable text. In `i18n/`, quotations are written as `{{quran:96:1}}` tokens, and the build
substitutes the wording of the edition registered in `i18n/quran.json`:

| | Edition | Licence |
|---|---|---|
| English | Marmaduke Pickthall, *The Meaning of the Glorious Koran* (1930) | Public domain — no permission or fee, which is why it was chosen over modern renderings still in copyright |
| German | Frank Bubenheim & Nadeem Elyas, *Der edle Qur'an* | King Fahd Complex edition, licensed for free distribution; attribution required |

Both were pulled from quran.com's API rather than typed from memory, and each generated file carries
a `quranTranslation` block whose `attribution` string **must be displayed** wherever a verse appears.
Three build-time guards enforce this: a `{{quran:}}` token that names an unregistered verse fails the
build, a translated string containing `﴿ ﴾` directly fails the build, and any Arabic letter surviving
into an `en`/`de` file fails the build. Swapping editions is a one-file change; entries also carry
`quranRefs` so the UI can link a quotation to its source. Six verses are registered: 96:1, 5:3,
19:56, 19:54, 21:85 and the phrase *fath mubin* (48:1).

**Emphasis handling.** Short label fields (`name`, `people`, `book.text`, `placeText`) are stripped
of markdown. Long fields (`sinsAndPunishment`, `message`, `summary`) keep inline `**bold**`, which
marks key terms and quoted verses — render them with an inline-markdown renderer, not `innerHTML`.

## Open items

1. **The English and German translations are unreviewed.** Every translated file carries
   `translation.status: "machine"`. They are complete and consistent, but no human has read them
   against the Arabic. A reviewer should work in `i18n/`, not in `content/`, then set
   `status: "reviewed"` with `reviewedBy` and `reviewedAt`. Until then the UI should badge these
   languages as unreviewed. The Qur'anic quotations are the exception — they are published editions
   and need no linguistic review, only that the attribution stays visible.

2. **Eight locations still have no image**: `mount-safa`, `hamra-al-asad`, `hunayn`, `al-abwa`,
   `badiyat-bani-saad`, `mecca-medina-road`, `midyan` and `paradise` (non-geographic). Commons had
   nothing that faithfully depicts them, and a lookalike would misrepresent the place, so they stay
   null and the UI renders those panels without an image. The other 32 carry a Wikimedia Commons
   file under a free licence (CC0 / CC BY / CC BY-SA / public domain), with credit, licence and a
   link to the file page — all three must stay visible in any UI. Images were checked by eye as
   well as by licence: the first pass returned a bird's nest for Badr and a football pitch for
   Ta'if, both of which passed every automated check.

3. **Three locations exist in the registry but no row points at them**: `tabuk`, `dumat-al-jandal`,
   `al-khandaq`. The source's place column gives the *departure* point (المدينة) for events 93, 70
   and 71 rather than where the event happened. Decide per event whether to enrich `locations`
   manually — the build deliberately does not override the source on its own.

4. **Coordinates are curated, not sourced.** They are good enough to place a map pin at the right
   scale; they are not a citation. Anything marked `traditional` or `disputed` should be checked
   against a historical atlas (e.g. الأطلس التاريخي لسيرة الرسول) before launch. The new route
   waypoints came from OpenStreetMap and Wikidata where the place still exists as a modern
   settlement (Usfan, Rabigh, Qudayd, Malal, Wadi Fatimah, al-Balqa); Amj is marked `disputed`.

5. **The Hijrah itinerary backtracks as listed.** Plotted strictly in the given order, stages 3–5
   run Usfan → al-Hudaybiyah → Batn Marr, which is roughly 60 km back to the south before the
   route resumes northward at Amj. The order is preserved exactly as supplied rather than silently
   corrected; moving Usfan after Batn Marr in `routes.json` would make the line run monotonically
   north if that matches the intended reading.

   
   