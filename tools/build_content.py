#!/usr/bin/env python3
"""Convert the authored Arabic markdown into the JSON the frontend fetches.

    python3 tools/build_content.py

Reads  : prophets-content, Mohammed-historical-events
Writes : web/content/*.json  (the published site serves these directly)

Arabic is the source of record. Every Arabic string in the output is copied
verbatim from the markdown — nothing is rewritten, summarised or re-dated here.
Everything this script adds (ids, slugs, location refs, sort years, categories)
is derived, and is either mechanical or comes from an explicit table below.

Re-runnable: delete the output and run again. Never hand-edit the Arabic JSON —
edit the markdown and rebuild, or the two drift apart.
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "content"
I18N = ROOT / "i18n"

LANGS = ("en", "de")
DIR_BY_LANG = {"ar": "rtl", "en": "ltr", "de": "ltr"}

# Arabic letters must not survive into a translated file. ﷺ (U+FDFA) is a
# presentation form outside this range and is intentionally kept in all
# languages, as is the Arabic-Indic-free Latin text around it.
ARABIC_LETTERS = re.compile(r"[؀-ۿ]")
QURAN_TOKEN = re.compile(r"\{\{quran:(\d+:\d+)\}\}")
QURAN_BRACKETS = re.compile(r"﴿[^﴾]*﴾")

# Quotation marks per language, so a rendered verse reads natively.
QUOTE_MARKS = {"en": ("“", "”"), "de": ("„", "“")}

# ---------------------------------------------------------------------------
# Curated tables. These encode judgements, not text — keep them reviewable.
# ---------------------------------------------------------------------------

# Prophet row number -> (id, short name, location ids, location certainty)
PROPHETS = {
    1:  ("adam",      "آدم",       ["paradise"],                        "unspecified"),
    2:  ("idris",     "إدريس",     [],                                  "unspecified"),
    3:  ("nuh",       "نوح",       [],                                  "unspecified"),
    4:  ("hud",       "هود",       ["al-ahqaf"],                        "traditional"),
    5:  ("salih",     "صالح",      ["al-hijr"],                         "traditional"),
    6:  ("ibrahim",   "إبراهيم",   ["mesopotamia", "ash-sham", "mecca"], "traditional"),
    7:  ("lut",       "لوط",       ["cities-of-lut"],                   "traditional"),
    8:  ("ismail",    "إسماعيل",   ["mecca"],                           "quranic"),
    9:  ("ishaq",     "إسحاق",     ["ash-sham"],                        "traditional"),
    10: ("yaqub",     "يعقوب",     ["ash-sham"],                        "traditional"),
    11: ("yusuf",     "يوسف",      ["egypt"],                           "quranic"),
    12: ("ayyub",     "أيوب",      ["ash-sham"],                        "traditional"),
    13: ("shuayb",    "شعيب",      ["midyan"],                          "quranic"),
    14: ("musa",      "موسى",      ["egypt", "sinai"],                  "quranic"),
    15: ("harun",     "هارون",     ["egypt", "sinai"],                  "quranic"),
    16: ("dawud",     "داود",      ["ash-sham", "jerusalem"],           "traditional"),
    17: ("sulayman",  "سليمان",    ["ash-sham", "jerusalem"],           "traditional"),
    18: ("ilyas",     "إلياس",     ["ash-sham"],                        "traditional"),
    19: ("al-yasa",   "اليسع",     ["ash-sham"],                        "traditional"),
    20: ("yunus",     "يونس",      ["nineveh"],                         "traditional"),
    21: ("dhul-kifl", "ذو الكفل",  [],                                  "unspecified"),
    22: ("zakariya",  "زكريا",     ["jerusalem", "ash-sham"],           "traditional"),
    23: ("yahya",     "يحيى",      ["jerusalem", "ash-sham"],           "traditional"),
    24: ("isa",       "عيسى",      ["jerusalem", "ash-sham"],           "quranic"),
    25: ("muhammad",  "محمد",      ["mecca", "medina"],                 "quranic"),
}

# Books the Qur'an names explicitly (section 1 of the source document).
BOOKS = {
    "ibrahim": "suhuf-ibrahim",
    "musa": "tawrah",
    "harun": "tawrah",
    "dawud": "zabur",
    "isa": "injil",
    "muhammad": "quran",
}

# Sin categories, taken only where section 6 of the source names the people
# explicitly. Prophets absent here get no `sins` field rather than a guess.
SINS = {
    "nuh": ["shirk", "arrogance"],
    "hud": ["shirk", "arrogance"],
    "salih": ["shirk", "arrogance"],
    "ibrahim": ["shirk"],
    "lut": ["shirk", "moral-corruption"],
    "shuayb": ["shirk", "economic-corruption"],
    "musa": ["shirk", "arrogance", "tyranny"],
    "harun": ["shirk"],
    "ilyas": ["shirk"],
    "isa": ["distortion-of-religion"],
    "muhammad": ["shirk", "arrogance"],
}

# Sections 3 and 4. parentId only where the source states father-to-son.
LINEAGE = {
    "adam": {"branch": "pre-abrahamic"},
    "idris": {"branch": "pre-abrahamic"},
    "nuh": {"branch": "pre-abrahamic"},
    "hud": {"branch": "other"},
    "salih": {"branch": "other"},
    "ibrahim": {"branch": "other"},
    "lut": {"branch": "other", "contemporaryOf": ["ibrahim"]},
    "ismail": {"branch": "ismaili", "parentId": "ibrahim"},
    "ishaq": {"branch": "israelite", "parentId": "ibrahim"},
    "yaqub": {"branch": "israelite", "parentId": "ishaq"},
    "yusuf": {"branch": "israelite", "parentId": "yaqub"},
    "ayyub": {"branch": "other"},
    "shuayb": {"branch": "other"},
    "musa": {"branch": "israelite"},
    "harun": {"branch": "israelite", "contemporaryOf": ["musa"]},
    "dawud": {"branch": "israelite"},
    "sulayman": {"branch": "israelite", "parentId": "dawud"},
    "ilyas": {"branch": "israelite"},
    "al-yasa": {"branch": "israelite"},
    "yunus": {"branch": "other"},
    "dhul-kifl": {"branch": "other"},
    "zakariya": {"branch": "israelite"},
    "yahya": {"branch": "israelite", "parentId": "zakariya"},
    "isa": {"branch": "israelite"},
    "muhammad": {"branch": "ismaili"},
}

# The six sections of the events document, in order.
ERAS = [
    ("pre-birth-and-childhood",        "أولًا: ما قبل مولد النبي ﷺ والولادة والطفولة"),
    ("prophethood-and-meccan-daawah",  "ثانيًا: بداية النبوة والدعوة المكية"),
    ("hijrah-and-medina",              "ثالثًا: الهجرة وتأسيس مجتمع المدينة"),
    ("hudaybiyah-khaybar-and-beyond",  "رابعًا: الحديبية وخيبر والمرحلة الدولية"),
    ("conquest-of-mecca",              "خامسًا: فتح مكة وما بعده"),
    ("tabuk-and-the-completed-state",  "سادسًا: تبوك وعام الوفود واكتمال الدولة"),
]

EVENT_SLUGS = {
    1: "quraysh-and-mecca", 2: "year-of-the-elephant", 3: "death-of-abdullah",
    4: "birth-of-the-prophet", 5: "naming-muhammad", 6: "nursing-with-halimah",
    7: "first-splitting-of-the-breast", 8: "return-to-his-mother",
    9: "aminah-visits-medina", 10: "death-of-aminah",
    11: "guardianship-of-abd-al-muttalib", 12: "death-of-abd-al-muttalib",
    13: "guardianship-of-abu-talib", 14: "journey-to-al-sham-with-abu-talib",
    15: "harb-al-fijar", 16: "hilf-al-fudul", 17: "trading-for-khadijah",
    18: "marriage-to-khadijah", 19: "family-and-trade-life",
    20: "rebuilding-the-kaaba", 21: "seclusion-in-hira",
    22: "first-revelation", 23: "return-to-khadijah", 24: "waraqah-ibn-nawfal",
    25: "islam-of-khadijah", 26: "islam-of-ali", 27: "islam-of-zayd-ibn-harithah",
    28: "islam-of-abu-bakr", 29: "secret-daawah-phase",
    30: "islam-of-uthman-zubayr-talhah-saad", 31: "public-proclamation",
    32: "calling-quraysh-at-al-safa", 33: "intensifying-persecution",
    34: "first-migration-to-abyssinia", 35: "second-migration-to-abyssinia",
    36: "islam-of-hamzah", 37: "islam-of-umar", 38: "the-negus-and-the-migrants",
    39: "boycott-of-banu-hashim", 40: "end-of-the-boycott",
    41: "death-of-abu-talib", 42: "death-of-khadijah", 43: "year-of-sorrow",
    44: "journey-to-taif", 45: "islam-of-people-of-yathrib",
    46: "first-pledge-of-aqabah", 47: "sending-musab-ibn-umayr",
    48: "second-pledge-of-aqabah", 49: "permission-to-migrate",
    50: "quraysh-conspiracy",
    51: "the-hijrah", 52: "stay-in-cave-thawr", 53: "suraqah-ibn-malik",
    54: "arrival-at-quba", 55: "entering-medina",
    56: "building-the-prophets-mosque", 57: "brotherhood-muhajirun-ansar",
    58: "constitution-of-medina", 59: "beginning-of-medinan-legislation",
    60: "change-of-qiblah", 61: "battle-of-badr",
    62: "captives-and-losses-of-quraysh", 63: "banu-qaynuqa",
    64: "quraysh-prepares-for-uhud", 65: "battle-of-uhud", 66: "hamra-al-asad",
    67: "banu-al-nadir", 68: "dhat-al-riqa", 69: "badr-al-mawid",
    70: "dumat-al-jandal", 71: "battle-of-the-trench",
    72: "failure-of-the-siege", 73: "banu-qurayzah", 74: "shift-to-negotiation",
    75: "setting-out-to-hudaybiyah", 76: "quraysh-blocks-entry",
    77: "pledge-of-ridwan", 78: "treaty-of-hudaybiyah", 79: "letters-to-kings",
    80: "battle-of-khaybar", 81: "ali-at-khaybar", 82: "umrat-al-qada",
    83: "battle-of-mutah", 84: "islam-of-khalid-and-amr",
    85: "breach-of-the-treaty", 86: "march-to-mecca", 87: "conquest-of-mecca",
    88: "islam-of-abu-sufyan", 89: "general-amnesty", 90: "battle-of-hunayn",
    91: "siege-of-taif", 92: "tribal-delegations-after-the-conquest",
    93: "expedition-of-tabuk", 94: "those-who-stayed-behind-at-tabuk",
    95: "year-of-delegations", 96: "abu-bakr-leads-the-hajj",
    97: "islam-spreads-across-arabia", 98: "expedition-of-usamah-ibn-zayd",
    99: "setting-out-for-the-farewell-hajj", 100: "farewell-hajj",
    101: "farewell-sermon", 102: "verse-of-completion-of-the-religion",
    103: "return-to-medina", 104: "onset-of-the-prophets-illness",
    105: "abu-bakr-leads-the-prayer",
    106: "the-prophet-looks-upon-the-praying-muslims",
    107: "death-of-the-prophet", 108: "burial-of-the-prophet",
}

# Date-certainty grades, assigned only to events the source names in its
# A/B/C section. Everything else stays null — null means "the source did not
# grade this", never "graded and fine".
DATE_GRADES = {
    61: "A",   # بدر
    65: "A",   # أحد
    71: "A",   # الخندق
    78: "A",   # الحديبية
    87: "A",   # فتح مكة
    100: "A",  # حجة الوداع
    107: "A",  # الوفاة
    4: "B",    # مولده ﷺ
    14: "C",   # رحلة بحيرى
    15: "C",   # حرب الفجار
    17: "C",   # الرحلات التجارية
}

# The source explicitly flags this row as needing separate study.
NEEDS_SEPARATE_STUDY = {73}

# Events that are journeys. The itinerary itself lives in content/routes.json;
# this only says which event carries which route. `locations` is left exactly as
# the source's place column gave it — the route is drawn in addition to it, not
# instead of it.
ROUTES = {
    51: "hijrah",            # Mecca → cave of Thawr → ... → Quba → Medina
    93: "medina-tabuk",
    96: "medina-mecca-hajj",
    98: "medina-balqa",
}

# Verbatim place cell -> location ids, in the order they appear in the cell.
PLACES = {
    "مكة": ["mecca"],
    "المدينة": ["medina"],
    "يثرب": ["medina"],
    "مكة → المدينة": ["mecca", "medina"],
    "المدينة → مكة": ["medina", "mecca"],
    "المدينة/مكة": ["medina", "mecca"],
    "مكة واليمن": ["mecca", "yemen"],
    "مكة → بادية بني سعد": ["mecca", "badiyat-bani-saad"],
    "بادية بني سعد": ["badiyat-bani-saad"],
    "بادية بني سعد → مكة": ["badiyat-bani-saad", "mecca"],
    "الأبواء": ["al-abwa"],
    "طريق الشام": ["sham-route"],
    "مكة → الشام": ["mecca", "ash-sham"],
    "مكة – غار حراء": ["cave-hira"],
    "غار حراء، مكة": ["cave-hira"],
    "جبل الصفا، مكة": ["mount-safa"],
    "مكة → الحبشة": ["mecca", "abyssinia"],
    "الحبشة": ["abyssinia"],
    "مكة → الطائف": ["mecca", "taif"],
    "الطائف": ["taif"],
    "العقبة، منى": ["al-aqabah"],
    "العقبة": ["al-aqabah"],
    "مكة → غار ثور": ["mecca", "cave-thawr"],
    "غار ثور": ["cave-thawr"],
    "طريق مكة–المدينة": ["mecca-medina-road"],
    "قباء": ["quba"],
    "بدر": ["badr"],
    "جبل أحد": ["mount-uhud"],
    "حمراء الأسد": ["hamra-al-asad"],
    "نجد": ["najd"],
    "المدينة → الحديبية": ["medina", "al-hudaybiyah"],
    "الحديبية": ["al-hudaybiyah"],
    "خيبر": ["khaybar"],
    "مؤتة": ["mutah"],
    "حنين": ["hunayn"],
    "الجزيرة العربية": ["arabian-peninsula"],
    "مكة وعرفات ومزدلفة ومنى": ["mecca", "arafat", "muzdalifah", "mina"],
    "عرفات": ["arafat"],
}

SOURCES = [
    {"id": "worldhistory", "label": "Weltgeschichte Enzyklopädie / World History Encyclopedia",
     "url": "https://www.worldhistory.org/timeline/Prophet_Muhammad/"},
    {"id": "pbs", "label": "PBS — Muhammad: Legacy of a Prophet",
     "url": "https://www.pbs.org/muhammad/timeline_html.shtml"},
    {"id": "islamicchronicles", "label": "Muslim History Chronicles",
     "url": "https://islamicchronicles.com/islamic-history/rise-of-islam/chronological-biography-of-prophet-muhammad/"},
]
SOURCE_BY_MARKER = {"1": "worldhistory", "2": "pbs", "3": "islamicchronicles"}

QURAN_SOURCE = [{"id": "quran-com", "label": "Quran.com", "url": "https://quran.com/"}]

DATE_CAVEAT = (
    "التاريخ الهجري قمري، ولا يصح تحويل كل تاريخ هجري قديم إلى تاريخ ميلادي "
    "وكأنه محسوب بدقة من تقويم ثابت؛ فالمصادر الحديثة تختلف في المقابلة بين "
    "التاريخين. والتواريخ الميلادية هنا تقريبية."
)

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

SOURCE_REF = re.compile(r"\(\[[^\]]+\]\[(\d)\]\)")
BOLD_LEAD = re.compile(r"^\*\*(.+?)\*\*")
HIJRI_YEAR = re.compile(r"(\d+)(?:\s*[–—-]\s*\d+)?\s*(ق\.\s*هـ|هـ)")
GREGORIAN_YEAR = re.compile(r"(\d{3,4})")


def norm(s: str) -> str:
    """Normalise whitespace only. Arabic letters are never touched."""
    return re.sub(r"\s+", " ", s.replace(" ", " ")).strip()


def unbold(s: str) -> str:
    return norm(s.replace("**", ""))


def table_rows(block: str):
    """Yield cell lists for numbered rows of a markdown table."""
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [norm(c) for c in line.strip("|").split("|")]
        if not re.fullmatch(r"\*\*\d+\*\*", cells[0]):
            continue
        yield int(cells[0].strip("*")), cells


def extract_sources(text: str):
    ids = [SOURCE_BY_MARKER[m] for m in SOURCE_REF.findall(text)]
    return norm(SOURCE_REF.sub("", text)), list(dict.fromkeys(ids))


def hijri_sort_year(cell: str):
    """Derived sort key. Negative before the Hijra. Start of a range."""
    m = HIJRI_YEAR.search(cell)
    if not m:
        return None
    year = int(m.group(1))
    return -year if m.group(2).replace(" ", "") == "ق.هـ" else year


def gregorian_sort_year(cell: str):
    m = GREGORIAN_YEAR.search(cell)
    return int(m.group(1)) if m else None


def split_event_cell(cell: str):
    """'**Title** ✓ qualifier: summary' -> (title, mark, qualifier, summary)."""
    lead = BOLD_LEAD.match(cell)
    if not lead:
        raise ValueError(f"event cell has no bold title: {cell[:60]}")
    title = norm(lead.group(1))
    rest = cell[lead.end():]

    mark, qualifier, summary = "unmarked", None, rest
    head, sep, tail = rest.partition(":")
    if sep and len(head) <= 40:
        summary = tail
        head = norm(head)
        if "✓/≈" in head or "✓ /≈" in head:
            mark = "mixed"
        elif "✓" in head:
            mark = "verified"
        elif "≈" in head:
            mark = "approximate"
        qualifier = norm(head.replace("✓", "").replace("≈", "").replace("/", "")) or None
    return title, mark, qualifier, norm(summary)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def build_prophets(md: str) -> dict:
    block = md.split("# ملاحظات مهمة حول الجدول", 1)[0]
    out = []
    for num, cells in table_rows(block):
        if len(cells) != 7:
            raise ValueError(f"prophet row {num}: expected 7 cells, got {len(cells)}")
        pid, short, locs, loc_certainty = PROPHETS[num]
        book_text = unbold(cells[3])
        entry = {
            "id": pid,
            "order": num,
            "name": unbold(cells[1]),
            "shortName": short,
            "people": unbold(cells[2]),
            "book": {
                "text": book_text,
                "namedInQuran": pid in BOOKS,
                "bookId": BOOKS.get(pid),
            },
            "sinsAndPunishment": norm(cells[4]),
            "message": norm(cells[5]),
            "placeText": unbold(cells[6]),
            "locations": locs,
            "locationCertainty": loc_certainty,
        }
        if pid in SINS:
            entry["sins"] = SINS[pid]
        if pid in LINEAGE:
            entry["lineage"] = LINEAGE[pid]
        if pid == "muhammad":
            entry["detailPage"] = "muhammad"
        out.append(entry)

    if len(out) != 25:
        raise ValueError(f"expected 25 prophets, parsed {len(out)}")
    return {
        "$schema": "../../schema/prophets.schema.json",
        "version": 1,
        "lang": "ar",
        "dir": "rtl",
        "translation": {"status": "source", "from": "ar", "reviewedBy": None, "reviewedAt": None},
        "source": {
            "file": "prophets-content",
            "generatedBy": "tools/build_content.py",
            "generatedAt": date.today().isoformat(),
        },
        "sources": QURAN_SOURCE,
        "prophets": out,
    }


def build_events(md: str) -> dict:
    body = md.split("# الأحداث الـ108", 1)[0]
    sections = re.split(r"^# ", body, flags=re.M)[1:]
    if len(sections) != len(ERAS):
        raise ValueError(f"expected {len(ERAS)} eras, found {len(sections)}")

    events, eras = [], []
    for (era_id, era_title), section in zip(ERAS, sections):
        heading = norm(section.splitlines()[0])
        if heading != era_title:
            raise ValueError(f"era heading drifted:\n  expected {era_title}\n  found    {heading}")

        ids_in_era = []
        for num, cells in table_rows(section):
            if len(cells) != 5:
                raise ValueError(f"event row {num}: expected 5 cells, got {len(cells)}")
            detail, src_ids = extract_sources(cells[4])
            title, mark, qualifier, summary = split_event_cell(detail)
            place = cells[3].replace("**", "")
            if place not in PLACES:
                raise ValueError(f"event {num}: unmapped place {place!r} — add it to PLACES")

            authenticity = {"mark": mark, "qualifier": qualifier, "grade": DATE_GRADES.get(num)}
            if num in NEEDS_SEPARATE_STUDY:
                authenticity["needsSeparateStudy"] = True

            event = {
                "id": num,
                "slug": EVENT_SLUGS[num],
                "eraId": era_id,
                "order": num,
                "title": title,
                "summary": summary,
                "date": {
                    "hijri": unbold(cells[1]),
                    "gregorian": unbold(cells[2]),
                    "sortYearHijri": hijri_sort_year(cells[1]),
                    "sortYearGregorian": gregorian_sort_year(cells[2]),
                },
                "authenticity": authenticity,
                "placeText": place,
                "locations": PLACES[place],
                "movement": "→" in place,
            }
            if num in ROUTES:
                event["routeId"] = ROUTES[num]
            if src_ids:
                event["sources"] = src_ids
            events.append(event)
            ids_in_era.append(num)

        eras.append({
            "id": era_id,
            "order": len(eras) + 1,
            "title": era_title,
            "firstEvent": min(ids_in_era),
            "lastEvent": max(ids_in_era),
        })

    if [e["id"] for e in events] != list(range(1, 109)):
        raise ValueError("events are not exactly 1..108 in order")
    return {
        "$schema": "../../schema/muhammad.schema.json",
        "version": 1,
        "lang": "ar",
        "dir": "rtl",
        "translation": {"status": "source", "from": "ar", "reviewedBy": None, "reviewedAt": None},
        "source": {
            "file": "Mohammed-historical-events",
            "generatedBy": "tools/build_content.py",
            "generatedAt": date.today().isoformat(),
        },
        "dateCaveat": DATE_CAVEAT,
        "sources": SOURCES,
        "eras": eras,
        "events": events,
    }


# ---------------------------------------------------------------------------
# Translation
# ---------------------------------------------------------------------------

def load_i18n():
    return {name: json.loads((I18N / f"{name}.json").read_text(encoding="utf-8"))
            for name in ("quran", "common", "prophets", "events")}


def render_quote(quran: dict, ref: str, lang: str) -> str:
    """Render a verse in the published edition for `lang`, with its reference.

    This is the ONLY place a non-Arabic Qur'anic wording is produced. Nothing
    else may translate a verse — see i18n/quran.json.
    """
    quote = quran["quotes"][ref]
    open_q, close_q = QUOTE_MARKS[lang]
    return f"{open_q}{quote[lang]}{close_q} ({quote['surah'][lang]} {ref})"


def resolve_quotes(text: str, quran: dict, lang: str, where: str):
    """Replace {{quran:s:a}} tokens; return (text, refs used)."""
    refs = []

    def sub(match):
        ref = match.group(1)
        if ref not in quran["quotes"]:
            raise ValueError(f"{where}: unknown Qur'an reference {ref!r} — add it to i18n/quran.json")
        refs.append(ref)
        return render_quote(quran, ref, lang)

    text = QURAN_TOKEN.sub(sub, text)
    if QURAN_BRACKETS.search(text):
        raise ValueError(f"{where}: a translated string contains Qur'anic text directly. "
                         f"Use a {{{{quran:s:a}}}} token so the published edition is used.")
    if ARABIC_LETTERS.search(text):
        raise ValueError(f"{where}: untranslated Arabic remains: {text[:60]!r}")
    return text, list(dict.fromkeys(refs))


def arabic_quran_refs(quran: dict, *texts) -> list:
    """Which registered quotes appear in these Arabic strings."""
    joined = " ".join(texts)
    refs = [ref for ref, q in quran["quotes"].items() if q["ar"] in joined]
    for found in QURAN_BRACKETS.findall(joined):
        if not any(quran["quotes"][r]["ar"] in found for r in refs):
            raise ValueError(f"Qur'anic quote not in i18n/quran.json: {found} — "
                             f"register it so the translations use a published edition")
    return refs


def lookup(table: dict, key: str, lang: str, kind: str) -> str:
    if key not in table:
        raise ValueError(f"no {kind} translation for {key!r} — add it to i18n/common.json")
    return table[key][lang]


def translate_prophets(base: dict, i18n: dict, lang: str) -> dict:
    quran, bundle = i18n["quran"], i18n["prophets"]["prophets"]
    doc = json.loads(json.dumps(base))
    doc["lang"] = lang
    doc["dir"] = DIR_BY_LANG[lang]
    doc["translation"] = {"status": "machine", "from": "ar", "reviewedBy": None, "reviewedAt": None}
    doc["quranTranslation"] = quran["editions"][lang]

    for prophet in doc["prophets"]:
        pid = prophet["id"]
        if pid not in bundle:
            raise ValueError(f"no translation for prophet {pid!r} in i18n/prophets.json")
        strings = bundle[pid][lang]
        refs = []
        for field in ("name", "shortName", "people", "sinsAndPunishment", "message", "placeText"):
            text, used = resolve_quotes(strings[field], quran, lang, f"prophets.{lang}:{pid}.{field}")
            prophet[field] = text
            refs += used
        prophet["book"]["text"], used = resolve_quotes(
            strings["book"], quran, lang, f"prophets.{lang}:{pid}.book")
        refs += used
        if refs:
            prophet["quranRefs"] = list(dict.fromkeys(refs))
    return doc


def translate_events(base: dict, i18n: dict, lang: str) -> dict:
    quran, common, bundle = i18n["quran"], i18n["common"], i18n["events"]["events"]
    doc = json.loads(json.dumps(base))
    doc["lang"] = lang
    doc["dir"] = DIR_BY_LANG[lang]
    doc["translation"] = {"status": "machine", "from": "ar", "reviewedBy": None, "reviewedAt": None}
    doc["quranTranslation"] = quran["editions"][lang]
    doc["dateCaveat"] = common["dateCaveat"][lang]

    for era in doc["eras"]:
        era["title"] = common["eras"][era["id"]][lang]

    for event in doc["events"]:
        key = str(event["id"])
        if key not in bundle:
            raise ValueError(f"no translation for event {key} in i18n/events.json")
        strings = bundle[key][lang]
        where = f"muhammad.{lang}:{key}"
        title, refs = resolve_quotes(strings["title"], quran, lang, where + ".title")
        summary, more = resolve_quotes(strings["summary"], quran, lang, where + ".summary")
        event["title"], event["summary"] = title, summary
        event["date"]["hijri"] = lookup(common["hijri"], event["date"]["hijri"], lang, "Hijri date")
        event["date"]["gregorian"] = lookup(
            common["gregorian"], event["date"]["gregorian"], lang, "Gregorian date")
        event["placeText"] = lookup(common["places"], event["placeText"], lang, "place")
        if event["authenticity"].get("qualifier"):
            event["authenticity"]["qualifier"] = lookup(
                common["qualifiers"], event["authenticity"]["qualifier"], lang, "qualifier")
        refs += more
        if refs:
            event["quranRefs"] = list(dict.fromkeys(refs))
    return doc


def annotate_arabic_quran_refs(prophets: dict, events: dict, quran: dict):
    """Tag the Arabic entries that quote the Qur'an, so the UI can link them."""
    for prophet in prophets["prophets"]:
        refs = arabic_quran_refs(quran, prophet["message"], prophet["sinsAndPunishment"],
                                 prophet["book"]["text"])
        if refs:
            prophet["quranRefs"] = refs
    for event in events["events"]:
        refs = arabic_quran_refs(quran, event["summary"])
        if refs:
            event["quranRefs"] = refs


def check_locations(*docs):
    """Every referenced location must exist. Report unused ones as a hint."""
    registry = json.loads((OUT / "locations.json").read_text(encoding="utf-8"))
    known = {loc["id"] for loc in registry["locations"]}
    routes = json.loads((OUT / "routes.json").read_text(encoding="utf-8"))["routes"]

    used = set()
    for doc in docs:
        for item in doc.get("prophets", []) + doc.get("events", []):
            used.update(item["locations"])
    for route in routes.values():
        used.update(route["waypoints"])

    missing = used - known
    if missing:
        raise ValueError(f"locations.json is missing: {sorted(missing)}")

    # A route must belong to the event that claims it, and vice versa.
    events = {e["id"]: e for doc in docs for e in doc.get("events", [])}
    for name, route in routes.items():
        event = events.get(route["eventId"])
        if not event:
            raise ValueError(f"route {name!r} points at unknown event {route['eventId']}")
        if event.get("routeId") != name:
            raise ValueError(f"route {name!r} claims event {route['eventId']}, "
                             f"but that event carries routeId {event.get('routeId')!r}")
    for event in events.values():
        if event.get("routeId") and event["routeId"] not in routes:
            raise ValueError(f"event {event['id']} references unknown route {event['routeId']!r}")

    by_id = {loc["id"]: loc for loc in registry["locations"]}
    for name, route in routes.items():
        drawn = [w for w in route["waypoints"] if by_id[w]["lat"] is not None]
        if len(drawn) < 2:
            raise ValueError(f"route {name!r} has fewer than two locatable waypoints")
        gaps = len(route["waypoints"]) - len(drawn)
        note = f", {gaps} unlocated (named but not pinned)" if gaps else ""
        print(f"  route {name}: {len(route['waypoints'])} waypoints, {len(drawn)} drawn{note}")

    unused = sorted(known - used)
    if unused:
        print(f"  note: {len(unused)} location(s) in the registry are not referenced "
              f"by any row or route: {', '.join(unused)}")


def write(path: Path, doc: dict):
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(ROOT)}  ({path.stat().st_size / 1024:.1f} KB)")


def main() -> int:
    OUT.mkdir(exist_ok=True)
    i18n = load_i18n()
    prophets = build_prophets((ROOT / "prophets-content").read_text(encoding="utf-8"))
    events = build_events((ROOT / "Mohammed-historical-events").read_text(encoding="utf-8"))
    annotate_arabic_quran_refs(prophets, events, i18n["quran"])
    check_locations(prophets, events)

    write(OUT / "prophets.ar.json", prophets)
    write(OUT / "muhammad.ar.json", events)
    for lang in LANGS:
        write(OUT / f"prophets.{lang}.json", translate_prophets(prophets, i18n, lang))
        write(OUT / f"muhammad.{lang}.json", translate_events(events, i18n, lang))

    print(f"  {len(prophets['prophets'])} prophets, {len(events['events'])} events, "
          f"{len(events['eras'])} eras in {len(LANGS) + 1} languages")
    print(f"  Qur'an: en = {i18n['quran']['editions']['en']['translator']}, "
          f"de = {i18n['quran']['editions']['de']['translator']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, KeyError) as err:
        print(f"build failed: {err}", file=sys.stderr)
        sys.exit(1)
