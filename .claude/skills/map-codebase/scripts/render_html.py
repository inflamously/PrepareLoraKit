#!/usr/bin/env python3
"""Render the code-map model into a single self-contained HTML page.

Exposes one function: render(model) -> str. The page has no external
requests; all CSS/JS is inline and the model JSON is embedded in a
<script type="application/json"> block. Views are hash-routed:
  #            meta map (package adjacency table)
  #g=<group>   group view
  #f=<path>    file view (defs, imports, referenced-by)
"""
from __future__ import annotations

import html
import json

_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Code Map — __TITLE__</title>
<style>
:root {
  --bg: #fbfaf8; --panel: #f2f0ec; --fg: #24211c; --muted: #79726a;
  --border: #ddd8d0; --accent: #8a5a00; --link: #1a56a0;
  --badge-bg: #e8e4dd; --warn: #a33a2a; --mono: ui-monospace, "Cascadia Code",
  Consolas, Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #17161a; --panel: #201f24; --fg: #e6e2da; --muted: #94908a;
    --border: #38363c; --accent: #d9a441; --link: #7fb0e8;
    --badge-bg: #2c2a31; --warn: #e08070;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 14px/1.5 system-ui, sans-serif; }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
code, .flink, .sym { font-family: var(--mono); font-size: 12.5px; }
header { display: flex; align-items: center; gap: 16px; padding: 8px 16px;
  border-bottom: 1px solid var(--border); background: var(--panel);
  position: sticky; top: 0; z-index: 2; }
header h1 { font-size: 15px; margin: 0; white-space: nowrap; }
header h1 a { color: var(--accent); }
#search { flex: 1; max-width: 420px; padding: 4px 10px; border-radius: 6px;
  border: 1px solid var(--border); background: var(--bg); color: var(--fg); }
#counts { color: var(--muted); font-size: 12px; white-space: nowrap; }
#layout { display: flex; height: calc(100vh - 46px); }
nav { width: 330px; min-width: 220px; overflow: auto; padding: 8px 4px 24px 8px;
  border-right: 1px solid var(--border); }
main { flex: 1; overflow: auto; padding: 18px 28px 60px; }
nav details { margin-left: 10px; }
nav > details { margin-left: 0; }
nav summary { cursor: pointer; color: var(--fg); font-weight: 600;
  font-size: 13px; padding: 1px 2px; user-select: none; }
nav summary .cnt { color: var(--muted); font-weight: 400; }
.tf { margin-left: 26px; padding: 0.5px 0; }
.tf a { color: var(--fg); }
.tf a:hover { color: var(--link); }
h2 { font-size: 17px; margin: 4px 0 12px; }
h2 .flink { font-size: 15px; }
h3 { font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--muted); margin: 22px 0 6px; }
table { border-collapse: collapse; width: 100%; max-width: 1100px; }
th, td { text-align: left; padding: 6px 14px 6px 0; vertical-align: top;
  border-bottom: 1px solid var(--border); font-size: 13px; }
th { color: var(--muted); font-weight: 600; }
ul.plain { list-style: none; margin: 0; padding: 0; }
ul.plain li { padding: 2px 0; }
.badge { display: inline-block; padding: 0 7px; border-radius: 9px;
  background: var(--badge-bg); color: var(--muted); font-size: 11px;
  margin-left: 6px; vertical-align: 1px; }
.badge.warn { color: var(--warn); }
.ln { color: var(--muted); font-size: 11.5px; margin-left: 4px; }
.sym { color: var(--accent); }
.muted { color: var(--muted); }
.defkind { color: var(--muted); font-size: 12px; display: inline-block;
  width: 62px; }
.method { margin-left: 76px; }
.err { color: var(--warn); border: 1px solid var(--warn); border-radius: 6px;
  padding: 6px 10px; margin: 10px 0; display: inline-block; }
.notice { color: var(--muted); font-style: italic; margin-bottom: 14px; }
</style>
</head>
<body>
<header>
  <h1><a href="#">Code Map — __TITLE__</a></h1>
  <input id="search" type="search" placeholder="filter files and definitions…"
    autocomplete="off">
  <span id="counts"></span>
</header>
<div id="layout">
  <nav id="tree"></nav>
  <main id="view"></main>
</div>
<script type="application/json" id="cm-data">__DATA__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById("cm-data").textContent);
const FILES = DATA.files;
const byPath = new Map(FILES.map(f => [f.p, f]));
const FLAGS = { tc: "type-only", st: "star", dy: "dynamic", re: "re-export",
  mod: "module" };
const KINDS = { c: "class", f: "function", v: "const" };

const REV = new Map();
for (const f of FILES) for (const e of f.i || []) {
  if (!REV.has(e.t)) REV.set(e.t, []);
  REV.get(e.t).push({ p: f.p, s: e.s, f: e.f || [] });
}
for (const list of REV.values()) list.sort((a, b) => a.p < b.p ? -1 : 1);

function groupOf(p) {
  const parts = p.split("/");
  return parts.length > 2 ? parts[0] + "/" + parts[1]
       : parts.length === 2 ? parts[0] : "(root)";
}
const GROUPS = new Map();
function grp(name) {
  if (!GROUPS.has(name)) GROUPS.set(name, { files: [], out: new Map(), inn: new Map() });
  return GROUPS.get(name);
}
for (const f of FILES) grp(groupOf(f.p)).files.push(f.p);
for (const f of FILES) for (const e of f.i || []) {
  const g = groupOf(f.p), tg = groupOf(e.t);
  if (tg === g) continue;
  grp(g).out.set(tg, (grp(g).out.get(tg) || 0) + 1);
  grp(tg).inn.set(g, (grp(tg).inn.get(g) || 0) + 1);
}
const GROUP_NAMES = [...GROUPS.keys()].sort();
const EDGE_COUNT = FILES.reduce((n, f) => n + (f.i || []).length, 0);

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") el.className = v; else el.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null) el.append(kid);
  return el;
}
const fileLink = p => h("a", { href: "#f=" + encodeURIComponent(p), class: "flink" }, p);
const groupLink = g => h("a", { href: "#g=" + encodeURIComponent(g), class: "flink" }, g);
const lnTag = ln => h("span", { class: "ln" }, ":" + ln);
const badge = (label, warn) =>
  h("span", { class: "badge" + (warn ? " warn" : "") }, label);
const flagBadges = fl => (fl || []).map(x => badge(FLAGS[x] || x));
const symList = s => s.length
  ? h("span", { class: "sym" }, " { " + s.join(", ") + " }") : null;

function groupCell(counts) {
  const names = [...counts.keys()].sort();
  if (!names.length) return h("span", { class: "muted" }, "—");
  return names.flatMap((g, i) => [
    i ? ", " : null, groupLink(g), h("span", { class: "ln" }, " (" + counts.get(g) + ")")]);
}

function renderMeta(view) {
  view.append(h("h2", null, "Meta map — packages"));
  view.append(h("div", { class: "notice" },
    "Groups are top two path levels. Edge counts are file-level import edges. " +
    "Click a group or pick a file from the tree."));
  const rows = GROUP_NAMES.map(g => h("tr", null,
    h("td", null, groupLink(g)),
    h("td", null, String(GROUPS.get(g).files.length)),
    h("td", null, groupCell(GROUPS.get(g).out)),
    h("td", null, groupCell(GROUPS.get(g).inn))));
  view.append(h("table", null,
    h("tr", null, h("th", null, "Group"), h("th", null, "Files"),
      h("th", null, "Imports \\u2192"), h("th", null, "\\u2190 Imported by")),
    rows));
}

function renderGroup(view, name) {
  const g = GROUPS.get(name);
  if (!g) { view.append(h("div", { class: "notice" }, "Unknown group: " + name)); return renderMeta(view); }
  view.append(h("h2", null, "Group ", h("span", { class: "flink" }, name)));
  view.append(h("h3", null, "Imports \\u2192"),
    h("div", null, groupCell(g.out)));
  view.append(h("h3", null, "\\u2190 Imported by"),
    h("div", null, groupCell(g.inn)));
  view.append(h("h3", null, "Files (" + g.files.length + ")"));
  view.append(h("ul", { class: "plain" },
    g.files.slice().sort().map(p => h("li", null, fileLink(p)))));
}

function defRows(f) {
  const rows = [];
  for (const d of f.d || []) {
    rows.push(h("li", null,
      h("span", { class: "defkind" }, KINDS[d.k] || d.k),
      h("span", { class: "sym" }, d.n), lnTag(d.ln)));
    for (const [m, ln] of d.m || [])
      rows.push(h("li", { class: "method" },
        h("span", { class: "sym" }, "." + m), lnTag(ln)));
  }
  return rows;
}

function renderFile(view, p) {
  const f = byPath.get(p);
  if (!f) { view.append(h("div", { class: "notice" }, "Unknown file: " + p)); return renderMeta(view); }
  view.append(h("h2", null, h("span", { class: "flink" }, f.p),
    badge(f.l), h("span", { class: "ln" }, " " + f.n + " lines"),
    " ", h("a", { href: "#g=" + encodeURIComponent(groupOf(f.p)), class: "ln" },
      "in " + groupOf(f.p))));
  if (f.err) view.append(h("div", { class: "err" }, f.err));

  view.append(h("h3", null, "Defines"));
  const defs = defRows(f);
  view.append(defs.length ? h("ul", { class: "plain" }, defs)
    : h("div", { class: "muted" }, "nothing top-level"));

  view.append(h("h3", null, "Imports"));
  const imps = (f.i || []).map(e => h("li", null,
    fileLink(e.t), symList(e.s), e.a ? h("span", { class: "muted" }, " as " + e.a) : null,
    lnTag(e.ln), flagBadges(e.f)));
  view.append(imps.length ? h("ul", { class: "plain" }, imps)
    : h("div", { class: "muted" }, "no internal imports"));

  const ext = f.e || [];
  for (const [g, label, warn] of [["std", "stdlib", false],
      ["ext", "third-party", false], ["unres", "unresolved", true]]) {
    const items = ext.filter(e => e.g === g);
    if (!items.length) continue;
    view.append(h("h3", null, "External — " + label));
    view.append(h("ul", { class: "plain" }, items.map(e => h("li", null,
      h("span", { class: "flink" }, e.m), symList(e.s), lnTag(e.ln),
      warn ? badge("unresolved", true) : null))));
  }

  view.append(h("h3", null, "Referenced by"));
  const refs = (REV.get(p) || []).map(r => h("li", null,
    fileLink(r.p), symList(r.s), flagBadges(r.f)));
  view.append(refs.length ? h("ul", { class: "plain" }, refs)
    : h("div", { class: "muted" }, "nothing in the map imports this file"));
}

function route() {
  const hash = decodeURIComponent(location.hash.slice(1));
  const view = document.getElementById("view");
  view.replaceChildren();
  if (hash.startsWith("f=")) renderFile(view, hash.slice(2));
  else if (hash.startsWith("g=")) renderGroup(view, hash.slice(2));
  else renderMeta(view);
  view.scrollTop = 0;
}

/* ---- sidebar tree ---- */
const SIDEBAR_FILES = [];
const SIDEBAR_DIRS = [];
function buildTree() {
  const root = { dirs: new Map(), files: [] };
  for (const f of FILES) {
    const parts = f.p.split("/");
    let node = root;
    for (const d of parts.slice(0, -1)) {
      if (!node.dirs.has(d)) node.dirs.set(d, { dirs: new Map(), files: [] });
      node = node.dirs.get(d);
    }
    node.files.push(f);
  }
  const count = n => n.files.length +
    [...n.dirs.values()].reduce((s, d) => s + count(d), 0);
  function renderNode(node, depth) {
    const out = [];
    for (const name of [...node.dirs.keys()].sort()) {
      const child = node.dirs.get(name);
      const det = h("details", depth < 1 ? { open: "", "data-top": "1" } : null,
        h("summary", null, name + "/ ",
          h("span", { class: "cnt" }, "(" + count(child) + ")")),
        renderNode(child, depth + 1));
      SIDEBAR_DIRS.push(det);
      out.push(det);
    }
    for (const f of node.files) {
      const base = f.p.split("/").pop();
      const el = h("div", { class: "tf" },
        h("a", { href: "#f=" + encodeURIComponent(f.p) }, base));
      const defNames = (f.d || []).flatMap(d =>
        [d.n, ...(d.m || []).map(m => m[0])]);
      SIDEBAR_FILES.push({ el, hay: (f.p + " " + defNames.join(" ")).toLowerCase() });
      out.push(el);
    }
    return out;
  }
  document.getElementById("tree").append(...renderNode(root, 0));
}

function applySearch(q) {
  q = q.trim().toLowerCase();
  for (const f of SIDEBAR_FILES) f.el.hidden = !!q && !f.hay.includes(q);
  for (let i = SIDEBAR_DIRS.length - 1; i >= 0; i--) {
    const d = SIDEBAR_DIRS[i];
    const visible = [...d.querySelectorAll(".tf")].some(el => !el.hidden);
    d.hidden = !!q && !visible;
    d.open = q ? visible : d.dataset.top === "1";
  }
}

buildTree();
document.getElementById("counts").textContent =
  FILES.length + " files \\u00b7 " + EDGE_COUNT + " edges";
document.getElementById("search").addEventListener("input",
  e => applySearch(e.target.value));
window.addEventListener("hashchange", route);
route();
</script>
</body>
</html>
"""


def render(model: dict) -> str:
    """Return the full HTML page for a code-map model."""
    data = json.dumps(
        model, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).replace("</", "<\\/")
    head, tail = _TEMPLATE.split("__DATA__")
    title = html.escape(model["root"])
    return head.replace("__TITLE__", title) + data + tail.replace("__TITLE__", title)
