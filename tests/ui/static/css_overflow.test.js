/**
 * Guards the scrolling convention documented in
 * `prepare_lora_kit_ui/static/core/foundation.css`.
 *
 * The bug this exists to prevent is not a typo, it is a default: when one
 * overflow axis is not `visible`, the other computes from `visible` to `auto`.
 * So a pane that says only `overflow-y: auto` is silently a horizontal scroll
 * container too, and a strip that says only `overflow-x: auto` a vertical one.
 * Every axis must therefore be stated.
 *
 * Deliberately hand-rolled rather than run through jsdom's CSSOM: its `cssom`
 * backend drops properties it does not recognise (`overflow: clip`) and does not
 * normalise the shorthand, so it would report the opposite of the truth.
 */
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

const STATIC_DIR = fileURLToPath(
  new URL("../../../prepare_lora_kit_ui/static/", import.meta.url),
);

const SCROLLABLE = new Set(["auto", "scroll"]);

/** Comments are not decoration here — two stylesheets discuss `overflow:auto`
 *  in prose, and a scanner that reads them reports rules that do not exist. */
function stripComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

function matchingBrace(css, open) {
  let depth = 0;
  for (let i = open; i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    else if (css[i] === "}" && (depth -= 1) === 0) return i;
  }
  return css.length;
}

/** Flattens a stylesheet to style rules. `@media`/`@supports` bodies are walked
 *  into; `@keyframes` is skipped, because its `0%`/`50%` steps parse as
 *  selectors carrying declarations that were never about scrolling. */
function styleRules(css, into = []) {
  let cursor = 0;
  while (cursor < css.length) {
    const open = css.indexOf("{", cursor);
    if (open === -1) break;

    const prelude = css.slice(cursor, open).trim();
    const close = matchingBrace(css, open);
    const body = css.slice(open + 1, close);

    if (/^@(-\w+-)?keyframes\b/i.test(prelude)) {
      // skipped
    } else if (prelude.startsWith("@")) {
      styleRules(body, into);
    } else {
      into.push({ selector: prelude.replace(/\s+/g, " "), body });
    }
    cursor = close + 1;
  }
  return into;
}

function declarations(body) {
  const nested = body.indexOf("{");
  return body
    .slice(0, nested === -1 ? body.length : nested)
    .split(";")
    .map((entry) => entry.split(":"))
    .filter((parts) => parts.length >= 2)
    .map(([property, ...value]) => ({
      property: property.trim().toLowerCase(),
      value: value.join(":").trim().toLowerCase(),
    }));
}

/** Resolves a rule's overflow declarations the way the cascade would: the
 *  shorthand sets both axes (one value for both, or `<x> <y>`), and a later
 *  declaration of the same property wins — which is what makes the
 *  `hidden` then `clip` fallback pair read as a single `clip` intent. */
function overflowAxes(body) {
  const axes = { x: null, y: null, shorthands: [] };
  for (const { property, value } of declarations(body)) {
    if (property === "overflow") {
      const [x, y = x] = value.split(/\s+/);
      axes.shorthands.push(value);
      axes.x = x;
      axes.y = y;
    } else if (property === "overflow-x") {
      axes.x = value;
    } else if (property === "overflow-y") {
      axes.y = value;
    }
  }
  return axes;
}

function overflowRules(name, css) {
  return styleRules(stripComments(css))
    .map((rule) => ({ name, selector: rule.selector, axes: overflowAxes(rule.body) }))
    .filter(({ axes }) => axes.x !== null || axes.y !== null);
}

function unstatedAxis(rules) {
  return rules
    .filter(({ axes }) => axes.x === null || axes.y === null)
    .map(({ name, selector, axes }) => {
      const missing = axes.x === null ? "overflow-x" : "overflow-y";
      return `${name}: ${selector} declares only one axis, add ${missing}`;
    });
}

function scrollingShorthand(rules) {
  return rules
    .filter(({ axes }) =>
      axes.shorthands.some((value) =>
        value.split(/\s+/).some((part) => SCROLLABLE.has(part)),
      ),
    )
    .map(
      ({ name, selector }) =>
        `${name}: ${selector} scrolls via the \`overflow\` shorthand`,
    );
}

function projectRules() {
  return readdirSync(STATIC_DIR, { recursive: true })
    .map((entry) => String(entry))
    .filter((entry) => entry.endsWith(".css"))
    .flatMap((entry) =>
      overflowRules(
        entry.split(path.sep).join("/"),
        readFileSync(path.join(STATIC_DIR, entry), "utf8"),
      ),
    );
}

describe("css overflow scanner", () => {
  const scan = (css) => overflowRules("probe.css", css);

  it("flags a rule that states only one axis", () => {
    assert.deepEqual(unstatedAxis(scan(".pane { overflow-y: auto; }")), [
      "probe.css: .pane declares only one axis, add overflow-x",
    ]);
    assert.deepEqual(unstatedAxis(scan(".strip { overflow-x: auto; }")), [
      "probe.css: .strip declares only one axis, add overflow-y",
    ]);
  });

  it("accepts an axis paired with its hidden-then-clip fallback", () => {
    const rules = scan(
      ".pane { overflow-y: auto; overflow-x: hidden; overflow-x: clip; }",
    );
    assert.deepEqual(unstatedAxis(rules), []);
    assert.deepEqual(scrollingShorthand(rules), []);
    assert.equal(rules[0].axes.x, "clip", "the later declaration wins");
  });

  it("flags the shorthand only when it introduces scrolling", () => {
    assert.deepEqual(scrollingShorthand(scan(".a { overflow: auto; }")), [
      "probe.css: .a scrolls via the `overflow` shorthand",
    ]);
    assert.deepEqual(scrollingShorthand(scan(".b { overflow: hidden auto; }")), [
      "probe.css: .b scrolls via the `overflow` shorthand",
    ]);
    assert.deepEqual(scrollingShorthand(scan(".c { overflow: hidden; }")), []);
    assert.deepEqual(
      scrollingShorthand(scan(".d { overflow: hidden; overflow: clip; }")),
      [],
    );
  });

  it("reads the shorthand as setting both axes", () => {
    assert.deepEqual(unstatedAxis(scan(".a { overflow: hidden; }")), []);
    assert.deepEqual(scan(".b { overflow: hidden auto; }")[0].axes, {
      x: "hidden",
      y: "auto",
      shorthands: ["hidden auto"],
    });
  });

  it("ignores overflow written inside a comment", () => {
    assert.deepEqual(scan("/* .note { overflow: auto; } */ .a { color: red; }"), []);
    assert.deepEqual(
      unstatedAxis(scan(".a { /* overflow: auto */ overflow-y: auto; overflow-x: clip; }")),
      [],
    );
  });

  it("does not mistake text-overflow for overflow", () => {
    assert.deepEqual(scan(".a { text-overflow: ellipsis; }"), []);
  });

  it("skips @keyframes but walks into @media", () => {
    assert.deepEqual(
      scan("@keyframes pulse { 0% { overflow: auto; } 100% { opacity: 1; } }"),
      [],
    );
    assert.deepEqual(
      unstatedAxis(scan("@media (max-width: 900px) { .a { overflow-y: auto; } }")),
      ["probe.css: .a declares only one axis, add overflow-x"],
    );
  });

  it("keeps every selector of a multi-selector rule in the message", () => {
    assert.deepEqual(unstatedAxis(scan(".a,\n.b { overflow-y: auto; }")), [
      "probe.css: .a, .b declares only one axis, add overflow-x",
    ]);
  });
});

describe("css overflow convention", () => {
  it("finds the stylesheets it is meant to guard", () => {
    assert.ok(
      projectRules().length >= 40,
      "expected the static stylesheet tree to be discovered and parsed",
    );
  });

  it("states both axes wherever either one is declared", () => {
    const offenders = unstatedAxis(projectRules());
    assert.deepEqual(
      offenders,
      [],
      `The unstated axis computes to \`auto\`, not \`visible\`:\n${offenders.join("\n")}`,
    );
  });

  it("never introduces a scrollable axis through the shorthand", () => {
    const offenders = scrollingShorthand(projectRules());
    assert.deepEqual(
      offenders,
      [],
      `Write overflow-x and overflow-y explicitly so the intent is stated:\n${offenders.join("\n")}`,
    );
  });
});
