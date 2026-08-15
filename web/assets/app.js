/* Alseerah — a static frontend over the generated JSON.
 *
 * There is no backend. Content is fetched per language on demand:
 *   content/prophets.<lang>.json   content/muhammad.<lang>.json
 *   content/locations.json         (language-neutral, fetched once)
 *   content/routes.json            (journeys, fetched once)
 *
 * Route: #/<lang>/<view>[/<id>]   e.g. #/en/muhammad/61
 * Zoom is a view density, not a route — it is remembered in localStorage.
 */

import { UI, LANGS, DIR } from "./ui.js";

// content/ sits beside index.html both in the repo and in the published site,
// so this one relative path is correct in dev and in production.
const CONTENT = "content";
const ZOOM_MIN = 1, ZOOM_MAX = 3;

const state = {
  lang: "ar",
  view: "prophets",
  id: null,
  zoom: clampZoom(Number(localStorage.getItem("alseerah.zoom")) || 2),
  data: {},        // `${view}.${lang}` -> document
  locations: null, // id -> location
  routes: null,    // route id -> { waypoints, sourceNote }
  map: null,
};

const $ = (sel) => document.querySelector(sel);
const el = (tag, props = {}, ...kids) => {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.includes("-")) node.setAttribute(key, value); // aria-*, data-*
    else node[key] = value;
  }
  for (const kid of kids.flat()) if (kid != null) node.append(kid);
  return node;
};

function clampZoom(z) { return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z || 2)); }
function t() { return UI[state.lang]; }

/* ---------- inline markdown ----------
   Content keeps **bold** for key terms. Rendered by building nodes, never by
   assigning innerHTML — the strings include user-facing punctuation and quoted
   verses and must not be parsed as markup. */
function inlineMarkdown(text) {
  const frag = document.createDocumentFragment();
  for (const part of String(text ?? "").split(/(\*\*[^*]+\*\*)/g)) {
    if (!part) continue;
    if (part.startsWith("**") && part.endsWith("**")) frag.append(el("strong", { textContent: part.slice(2, -2) }));
    else frag.append(document.createTextNode(part));
  }
  return frag;
}

/* ---------- data ---------- */

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

async function ensureData(view, lang) {
  const key = `${view}.${lang}`;
  if (!state.data[key]) state.data[key] = await loadJSON(`${CONTENT}/${view}.${lang}.json`);
  if (!state.locations) {
    const [reg, routes] = await Promise.all([
      loadJSON(`${CONTENT}/locations.json`),
      loadJSON(`${CONTENT}/routes.json`),
    ]);
    state.locations = Object.fromEntries(reg.locations.map((l) => [l.id, l]));
    state.routes = routes.routes;
  }
  return state.data[key];
}

function entriesOf(doc, view) { return view === "prophets" ? doc.prophets : doc.events; }
function idOf(entry) { return String(entry.id); }

/* ---------- routing ---------- */

function parseHash() {
  const [lang, view, id] = location.hash.replace(/^#\/?/, "").split("/");
  return {
    lang: LANGS.includes(lang) ? lang : "ar",
    view: view === "muhammad" ? "muhammad" : "prophets",
    id: id ? decodeURIComponent(id) : null,
  };
}

function href(lang = state.lang, view = state.view, id = null) {
  return `#/${lang}/${view}${id ? "/" + encodeURIComponent(id) : ""}`;
}

async function route() {
  const next = parseHash();
  const changedList = next.lang !== state.lang || next.view !== state.view;
  Object.assign(state, next);

  document.documentElement.lang = state.lang;
  document.documentElement.dir = DIR[state.lang];
  applyChrome();

  $("#loading").hidden = false;
  let doc;
  try {
    doc = await ensureData(state.view, state.lang);
  } catch (err) {
    $("#loading").textContent = String(err.message);
    return;
  }
  $("#loading").hidden = true;

  if (changedList || !$("#timeline").childElementCount) renderTimeline(doc);
  renderDetail(doc);
  markActive();
  revealActive();
}

// Bring the open entry into view, once per selection, so opening a deep link
// lands on that point of the timeline instead of at the top.
let revealedId = null;
function revealActive() {
  if (!state.id || state.id === revealedId) { revealedId = state.id; return; }
  revealedId = state.id;
  const target = document.querySelector(`.node[data-id="${CSS.escape(state.id)}"]`);
  if (!target) return;

  // Only move if the entry is actually out of view, and jump rather than
  // animate — the list is long, and a smooth scroll across 90 entries is
  // both slow and disorienting.
  const box = target.getBoundingClientRect();
  const margin = 120;
  if (box.top >= margin && box.bottom <= window.innerHeight - margin) return;
  const y = window.scrollY + box.top - (window.innerHeight - box.height) / 2;
  window.scrollTo({ top: Math.max(0, y), behavior: "instant" });
}

/* ---------- chrome ---------- */

function applyChrome() {
  const s = t();
  document.title = `${s.siteTitle} — ${s.siteSubtitle}`;

  for (const node of document.querySelectorAll("[data-i18n]")) {
    const value = s[node.dataset.i18n];
    if (typeof value === "string") node.textContent = value;
  }
  for (const tab of document.querySelectorAll(".view-tab")) {
    tab.href = href(state.lang, tab.dataset.view);
    if (tab.dataset.view === state.view) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
  for (const btn of document.querySelectorAll(".lang-btn")) {
    btn.setAttribute("aria-pressed", String(btn.dataset.lang === state.lang));
  }
  $(".brand").href = href(state.lang, "prophets");

  $("#zoomLevel").textContent = s.zoomLevels[state.zoom - 1];
  $('[data-zoom="out"]').disabled = state.zoom === ZOOM_MIN;
  $('[data-zoom="in"]').disabled = state.zoom === ZOOM_MAX;

  $("#pageTitle").textContent = state.view === "prophets" ? s.prophetsTitle : s.muhammadTitle;
  $("#pageIntro").textContent = state.view === "prophets" ? s.prophetsIntro : s.muhammadIntro;

  const doc = state.data[`${state.view}.${state.lang}`];
  const notice = $("#translationNotice");
  const unreviewed = doc?.translation?.status === "machine";
  notice.hidden = !unreviewed;
  if (unreviewed) notice.textContent = s.unreviewed;

  const wrap = $(".timeline-wrap");
  wrap.className = `timeline-wrap zoom-${state.zoom}`;
}

/* ---------- timeline ---------- */

function badge(cls, text, title) {
  return el("span", { className: `badge ${cls}`, textContent: text, title: title || "" });
}

function markBadge(mark) { return badge(mark, t().marks[mark]); }

function gradeBadge(grade) {
  return grade ? badge(`grade grade-${grade}`, t().gradeLabel(grade), t().gradeHelp[grade]) : null;
}

function renderTimeline(doc) {
  const list = $("#timeline");
  list.replaceChildren();

  const jump = $("#eraJump");
  jump.replaceChildren();
  jump.hidden = state.view !== "muhammad";

  const entries = entriesOf(doc, state.view);
  const eras = state.view === "muhammad" ? doc.eras : null;
  let currentEra = null;

  for (const entry of entries) {
    if (eras && entry.eraId !== currentEra) {
      currentEra = entry.eraId;
      const era = eras.find((e) => e.id === currentEra);
      list.append(el("li", { className: "era-head", id: `era-${era.id}`, textContent: era.title }));
      jump.append(el("a", { className: "era-chip", href: `#era-${era.id}`, textContent: era.title.replace(/^[IVX]+\.\s*/, "") }));
    }
    list.append(node(entry));
  }

}

function node(entry) {
  const isProphet = state.view === "prophets";
  // Prophets have short names that sit inside the circle, as in the source
  // design. Event titles are full sentences in every language and would be
  // unreadable at that size, so their circle carries the sequence number and
  // the title sits beside it, where there is room to read it.
  const label = isProphet ? entry.shortName : String(entry.id);

  const meta = el("div", { className: "node-meta" });
  if (isProphet) {
    meta.append(el("span", {}, inlineMarkdown(entry.people)));
  } else {
    meta.append(el("span", { textContent: entry.date.hijri }));
    meta.append(markBadge(entry.authenticity.mark));
    const g = gradeBadge(entry.authenticity.grade);
    if (g) meta.append(g);
  }

  const button = el("button", { className: "node-btn", type: "button" },
    el("div", { className: "node-name", textContent: isProphet ? entry.name : entry.title }),
    meta,
    el("div", { className: "node-excerpt" }, inlineMarkdown(isProphet ? entry.message : entry.summary)));

  button.addEventListener("click", () => { location.hash = href(state.lang, state.view, idOf(entry)); });

  // The circle carries the name, as in the source design. Long names would
  // otherwise clip, so the label shrinks a step at a time to fit.
  const dot = el("span", { className: "node-dot", textContent: label, "aria-hidden": "true" });
  const len = [...label].length;
  if (isProphet) dot.style.setProperty("--label",
    len > 12 ? ".42rem" : len > 9 ? ".48rem" : len > 5 ? ".54rem" : ".62rem");
  else dot.classList.add("is-number");

  return el("li", { className: "node", dataset: { id: idOf(entry) } }, dot, button);
}

function markActive() {
  for (const li of document.querySelectorAll(".node")) {
    li.classList.toggle("is-active", li.dataset.id === state.id);
  }
}

/* ---------- detail ---------- */

function field(label, value, opts = {}) {
  if (value == null || value === "") return null;
  const dd = el("dd");
  dd.append(typeof value === "string" ? inlineMarkdown(value) : value);
  return el("div", { className: `field ${opts.lead ? "lead" : ""}` }, el("dt", { textContent: label }), dd);
}

function renderDetail(doc) {
  const panel = $("#detail");
  const scrim = $("#scrim");
  if (!state.id) {
    panel.hidden = true;
    scrim.hidden = true;
    document.body.classList.remove("detail-open");
    destroyMap();
    return;
  }

  const entries = entriesOf(doc, state.view);
  const index = entries.findIndex((e) => idOf(e) === state.id);
  if (index === -1) { location.hash = href(state.lang, state.view); return; }
  const entry = entries[index];
  const s = t();
  const isProphet = state.view === "prophets";

  const inner = $("#detailInner");
  destroyMap();
  inner.replaceChildren();

  const close = el("button", { className: "close-btn", type: "button", title: s.close, textContent: "✕" });
  close.setAttribute("aria-label", s.close);
  close.addEventListener("click", () => { location.hash = href(state.lang, state.view); });

  const eyebrow = isProphet
    ? `${entry.order} / ${entries.length}`
    : `${entry.id} / ${entries.length} · ${doc.eras.find((e) => e.id === entry.eraId).title}`;

  inner.append(el("div", { className: "detail-top" },
    el("div", {},
      el("div", { className: "detail-eyebrow", textContent: eyebrow }),
      el("h2", { id: "detailTitle", textContent: isProphet ? entry.name : entry.title })),
    close));

  // Certainty first: it qualifies everything below it.
  if (!isProphet) {
    const row = el("div", { className: "badge-row" });
    row.append(markBadge(entry.authenticity.mark));
    const g = gradeBadge(entry.authenticity.grade);
    row.append(g || badge("plain", s.noGrade));
    if (entry.authenticity.qualifier) row.append(badge("plain", entry.authenticity.qualifier));
    if (entry.authenticity.needsSeparateStudy) row.append(badge("approximate", s.needsStudy));
    inner.append(row);
  }

  const dl = el("dl", { className: "fields" });

  if (isProphet) {
    dl.append(
      field(s.message, entry.message, { lead: true }),
      field(s.people, entry.people),
      field(s.book, entry.book.text),
      field(s.sins, entry.sinsAndPunishment));
  } else {
    const dates = el("div", { className: "dates" },
      el("div", {}, el("b", { textContent: s.hijri }), el("span", { textContent: entry.date.hijri })),
      el("div", {}, el("b", { textContent: s.gregorian }), el("span", { textContent: entry.date.gregorian })));
    dl.append(field(s.summary, entry.summary, { lead: true }));
    const dateField = field(s.era, dates);
    dateField.querySelector("dt").textContent = s.dating;
    dateField.querySelector("dd").append(el("p", { className: "caveat", textContent: doc.dateCaveat }));
    dl.append(dateField);
  }

  // Place, then the map — and only if the source actually located it.
  const placeDd = el("dd");
  placeDd.append(inlineMarkdown(entry.placeText));
  const locs = entry.locations.map((id) => state.locations[id]).filter(Boolean);
  const geo = locs.filter((l) => l.lat != null);

  const tags = el("div", { className: "badge-row", style: "margin-top:.5rem;margin-bottom:0" });
  if (isProphet && entry.locationCertainty) tags.append(badge("plain", s.locationCertainty[entry.locationCertainty]));
  for (const l of locs) tags.append(badge("plain", `${l.name[state.lang]} — ${s.precision[l.precision]}`));
  if (tags.childElementCount) placeDd.append(tags);

  const route = entry.routeId ? state.routes[entry.routeId] : null;
  if (!geo.length && !route) placeDd.append(el("p", { className: "map-note", textContent: s.noMap }));
  dl.append(el("div", { className: "field" }, el("dt", { textContent: s.place }), placeDd));

  if (route) dl.append(itineraryField(route));
  inner.append(dl);

  // Image of the location. For a journey, show where it ends: the destination
  // is what the event is about, and it is also what the map's end marker points
  // at, so panel and map agree.
  const destination = routeLocations(route).at(-1);
  const shown = (destination?.image && destination) || locs.find((l) => l.image);
  if (shown) inner.append(figureFor(shown, shown === destination && Boolean(route)));

  // A route replaces the plain pins: it is the fuller statement of where the
  // event happened.
  const routePoints = routeLocations(route);
  const mapPoints = routePoints.length ? routePoints : geo;

  if (mapPoints.length) {
    const box = el("div", { className: "map", id: "mapBox" });
    inner.append(box);
    // Name the two ends in words as well as marking them by shape — colour and
    // shape alone are not enough on their own.
    if (routePoints.length > 1) inner.append(routeLegend(routePoints));
    if (mapPoints.some((l) => l.certainty === "disputed" || l.precision === "approximate")) {
      inner.append(el("p", { className: "map-note", textContent: s.disputedNote }));
    }
    requestAnimationFrame(() => showMap(box, mapPoints, Boolean(routePoints.length)));
  }

  // Attribution for the published Qur'an translation, where one is quoted.
  if (entry.quranRefs?.length && doc.quranTranslation) {
    inner.append(el("p", { className: "quran", textContent: doc.quranTranslation.attribution }));
  }

  if (isProphet && entry.detailPage === "muhammad") {
    inner.append(el("a", { className: "detail-cta", href: href(state.lang, "muhammad"), textContent: s.viewMuhammad }));
  }

  // Previous / next keeps the timeline browsable without closing the panel.
  const prev = el("button", { type: "button", disabled: index === 0 });
  const next = el("button", { type: "button", disabled: index === entries.length - 1 });
  prev.textContent = `← ${s.prev}`;
  next.textContent = `${s.next} →`;
  prev.addEventListener("click", () => go(index - 1, entries));
  next.addEventListener("click", () => go(index + 1, entries));
  inner.append(el("div", { className: "nav-pair" }, prev, next));

  panel.hidden = false;
  scrim.hidden = window.innerWidth > 860;
  document.body.classList.toggle("detail-open", window.innerWidth > 860);
  panel.scrollTop = 0;
  close.focus({ preventScroll: true });

}

function go(index, entries) {
  const entry = entries[index];
  if (entry) location.hash = href(state.lang, state.view, idOf(entry));
}

function figureFor(loc, isDestination = false) {
  const img = el("img", {
    src: loc.image.thumbUrl,
    alt: loc.name[state.lang],
    loading: "lazy",
    decoding: "async",
    referrerPolicy: "no-referrer",
  });
  // Wikimedia's thumbnail cache can miss; Special:FilePath always resolves.
  img.addEventListener("error", function onError() {
    img.removeEventListener("error", onError);
    img.src = loc.image.filePath + "?width=1200";
  }, { once: true });

  const s = t();
  const caption = el("figcaption", {},
    `${loc.name[state.lang]} · ${s.photoBy} ${loc.image.credit} (${loc.image.license}) `,
    el("a", { href: loc.image.descriptionUrl, target: "_blank", rel: "noopener noreferrer", textContent: s.viaCommons }));

  const figure = el("figure", { className: "figure" }, img, caption);
  if (isDestination) {
    figure.prepend(el("span", { className: "figure-tag", textContent: s.destination }));
    figure.classList.add("is-destination");
  }
  return figure;
}

// The located waypoints of a route, in order. Unlocatable stages are named in
// the itinerary but contribute no point, so they are skipped here.
function routeLocations(route) {
  if (!route) return [];
  const located = route.waypoints.map((id) => state.locations[id]).filter((l) => l && l.lat != null);

  // Collapse consecutive repeats. A route may legitimately pass the same place
  // twice — the Hijrah reaches Malal, goes on to al-Arj and Batn Ri'm, and comes
  // back through Malal — but those two are unlocated, so after filtering the two
  // Malals sit next to each other and would draw a zero-length segment with two
  // dots stacked on one pixel. The written itinerary still lists both, because
  // the traveller really did pass twice; only the drawing is collapsed.
  return located.filter((l, i) => i === 0 || l !== located[i - 1]);
}

function routeLegend(points) {
  const s = t();
  const key = (kind, loc) => el("span", { className: "legend-item" },
    el("span", { className: `map-pin is-${kind} is-inline` }, el("span", { className: "map-pin-glyph" })),
    el("span", {}, el("b", { textContent: s.routeEnds[kind] }), ` ${loc.name[state.lang]}`));
  return el("p", { className: "map-legend" },
    key("start", points[0]),
    key("end", points.at(-1)));
}

// The written itinerary: every stage in order, in the reader's language, with
// the ones that could not be located marked rather than quietly dropped.
function itineraryField(route) {
  const s = t();
  const list = el("ol", { className: "itinerary" });
  let unlocated = 0;

  for (const id of route.waypoints) {
    const loc = state.locations[id];
    if (!loc) continue;
    const item = el("li", {}, el("span", { textContent: loc.name[state.lang] }));
    if (loc.lat == null) {
      unlocated += 1;
      item.classList.add("is-unlocated");
      item.title = s.unlocatedHint;
    }
    list.append(item);
  }

  const dd = el("dd", {}, list);
  if (unlocated) dd.append(el("p", { className: "map-note", textContent: s.unlocatedNote(unlocated) }));
  if (route.sourceNote) dd.append(el("p", { className: "map-note", textContent: route.sourceNote[state.lang] }));

  return el("div", { className: "field" },
    el("dt", { textContent: `${s.itinerary} · ${route.waypoints.length}` }), dd);
}

/* ---------- map (Leaflet, vendored locally; tiles from OSM) ---------- */

const LEAFLET = new URL("vendor/leaflet/", document.baseURI);

function loadTag(tag, props) {
  return new Promise((resolve, reject) => {
    const node = el(tag, props);
    node.onload = resolve;
    node.onerror = () => reject(new Error(`failed to load ${props.href || props.src}`));
    document.head.append(node);
  });
}

let leafletReady = null;
function ensureLeaflet() {
  if (window.L) return Promise.resolve();
  if (!leafletReady) {
    leafletReady = Promise.all([
      // Wait for BOTH. Resolving on the script alone is a race: Leaflet works
      // out where its marker images live by reading the background-image of a
      // probe element styled by leaflet.css. Lose the race and it caches an
      // empty imagePath on the prototype, and every marker for the rest of the
      // session requests an icon URL that 404s. Locally the stylesheet is
      // instant so the race is always won, which is why this only showed up
      // once the site was on a real network.
      loadTag("link", { rel: "stylesheet", href: `${LEAFLET}leaflet.css` }),
      loadTag("script", { src: `${LEAFLET}leaflet.js` }),
    ]).then(() => {
      // Belt and braces: state the path outright so nothing is inferred from
      // CSS at all. Absolute, so it is correct under a project-page subpath.
      L.Icon.Default.imagePath = `${LEAFLET}images/`;
    });
  }
  return leafletReady;
}

// Built with divIcon rather than image pins: no new binary assets, it themes
// with the rest of the interface, and it stays crisp at any zoom.
function endpointIcon(kind) {
  // iconSize must match what the CSS actually draws, or Leaflet's anchor maths
  // put the mark off the point. The ring is centred on its coordinate; the
  // teardrop's sharp corner — which the CSS pins at (4, 26) by rotating about
  // that corner — is what sits on it.
  const end = kind === "end";
  return L.divIcon({
    className: "",                       // Leaflet's default draws a white box
    html: `<span class="map-pin is-${kind}"><span class="map-pin-glyph"></span></span>`,
    iconSize: end ? [22, 30] : [26, 26],
    iconAnchor: end ? [4, 26] : [13, 13],
    popupAnchor: end ? [9, -24] : [0, -15],
  });
}

function destroyMap() {
  if (state.map) { state.map.remove(); state.map = null; }
}

async function showMap(box, locs, isRoute = false) {
  try { await ensureLeaflet(); } catch { box.remove(); return; }
  if (!document.body.contains(box)) return;

  destroyMap();
  const map = L.map(box, { scrollWheelZoom: false, attributionControl: true });
  state.map = map;
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(map);

  const points = locs.map((l) => [l.lat, l.lon]);
  const accent = getComputedStyle(document.body).getPropertyValue("--accent").trim() || "#9a7325";

  if (points.length > 1) {
    L.polyline(points, { color: accent, weight: 2.5, opacity: .85, dashArray: "6 6" }).addTo(map);
  }

  const s = t();
  locs.forEach((l, i) => {
    const first = i === 0, last = i === locs.length - 1 && locs.length > 1;
    const place = `${l.name[state.lang]} — ${s.placeCertainty[l.certainty]}`;

    // A journey needs its direction readable at a glance, so the two ends are
    // deliberately different shapes and colours rather than two identical pins:
    // a hollow ring where it starts, a filled flag where it ends. Stages in
    // between are small dots, so a twenty-stage route stays legible.
    if (isRoute && (first || last)) {
      const kind = first ? "start" : "end";
      L.marker(points[i], {
        icon: endpointIcon(kind),
        zIndexOffset: 1000,
        title: `${s.routeEnds[kind]}: ${l.name[state.lang]}`,
      }).addTo(map).bindPopup(`<b>${s.routeEnds[kind]}</b><br>${place}`);
    } else if (isRoute) {
      L.circleMarker(points[i], {
        radius: 3.5, color: accent, weight: 2, opacity: .9,
        fillColor: "#fff", fillOpacity: 1,
      }).addTo(map).bindPopup(place);
    } else {
      L.marker(points[i]).addTo(map).bindPopup(place);
    }
  });

  if (points.length > 1) map.fitBounds(points, { padding: [34, 34] });
  else map.setView(points[0], locs[0].zoom ?? 10);
  setTimeout(() => map.invalidateSize(), 60);
}

/* ---------- events ---------- */

function setZoom(delta) {
  state.zoom = clampZoom(state.zoom + delta);
  localStorage.setItem("alseerah.zoom", String(state.zoom));
  applyChrome();
}

// Era chips scroll the list; they must not clobber the route.
$("#eraJump").addEventListener("click", (ev) => {
  const link = ev.target.closest("a");
  if (!link) return;
  ev.preventDefault();
  document.getElementById(link.hash.slice(1))?.scrollIntoView({ block: "start", behavior: "smooth" });
});

document.addEventListener("click", (ev) => {
  const zoomBtn = ev.target.closest(".zoom-btn");
  if (zoomBtn) return setZoom(zoomBtn.dataset.zoom === "in" ? 1 : -1);

  const langBtn = ev.target.closest(".lang-btn");
  if (langBtn) { location.hash = href(langBtn.dataset.lang, state.view, state.id); return; }

  if (ev.target.id === "scrim") location.hash = href(state.lang, state.view);
});

document.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape" && state.id) location.hash = href(state.lang, state.view);
  if (ev.target.matches("input, textarea")) return;
  if (ev.key === "+" || ev.key === "=") setZoom(1);
  if (ev.key === "-") setZoom(-1);
});

// Own the scroll position: the browser's restoration would otherwise undo the
// jump to a deep-linked entry on reload.
if ("scrollRestoration" in history) history.scrollRestoration = "manual";

window.addEventListener("hashchange", route);
window.addEventListener("load", () => {
  if (!location.hash) {
    const preferred = LANGS.find((l) => navigator.language?.toLowerCase().startsWith(l)) || "ar";
    location.replace(href(preferred, "prophets"));
  }
  route();
});
