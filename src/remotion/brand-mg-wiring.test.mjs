/**
 * RULE 1 GATE for the SIXTH LINK — the one that produces PIXELS.
 *
 *   node src/remotion/brand-mg-wiring.test.mjs        # exit 0 = PASS
 *
 * WHAT ROTTED BEFORE. Components D (name-plate) and F (end-card) were complete
 * through five links — producer, image-mount, call site, response schema,
 * guidance — and rendered nothing on 100% of jobs, because neither name was a
 * key in PromptlyRender's MG_MAP and nothing turned `edit_plan["_brand_specs"]`
 * into render props. cert_component_completeness.py ends deliberately at
 * REQUESTABLE + TAUGHT and printed that gap as an INFO line every run
 * ("NOT-YET-RENDERABLE") rather than failing on it. This file is the assertion
 * that INFO line was standing in for.
 *
 * IT PARSES SOURCE, IT DOES NOT IMPORT. PromptlyRender.tsx pulls in `remotion`,
 * `@remotion/media` and eight google-font packages; src/remotion/node_modules is
 * not installed in a worker checkout and installing it would need the network.
 * A gate that only runs where deps happen to exist is a gate that silently stops
 * running — so this one reads the files, offline, $0, in ~30ms.
 *
 * EVERYTHING IS DERIVED. The style-field list comes out of brand_components.py,
 * the MG vocabulary out of type_registries.py, the dispatch keys out of
 * PromptlyRender.tsx. There is no hand-typed component list anywhere below: a
 * hand-typed list is the same defect one file over, which is the lesson
 * cert_component_completeness.py already paid for.
 */
import assert from "node:assert";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..", "..");
const read = (p) => readFileSync(join(REPO, p), "utf8");

const RENDER = read("src/remotion/PromptlyRender.tsx".replace("src/remotion/", "src/remotion/src/"));
const TYPES_TS = read("src/remotion/src/types.ts");
const ADAPTER = read("src/remotion/src/motion-graphics/brand/BrandSpecMG.tsx");
const BARREL = read("src/remotion/src/motion-graphics/index.ts");
const BRAND_PY = read("brand_components.py");
const REGISTRY_PY = read("type_registries.py");
const NAMEPLATE = read("src/remotion/src/motion-graphics/NamePlate/NamePlate.tsx");
const NAMEPLATE_T = read("src/remotion/src/motion-graphics/NamePlate/types.ts");
const ENDCARD = read("src/remotion/src/motion-graphics/EndCard/EndCard.tsx");
const ENDCARD_T = read("src/remotion/src/motion-graphics/EndCard/types.ts");

let passed = 0;
const check = (name, fn) => {
  try {
    fn();
    passed++;
    console.log(`  ok   ${name}`);
  } catch (e) {
    console.error(`  FAIL ${name}\n       ${e.message}`);
    process.exitCode = 1;
  }
};

// ── Derivations ─────────────────────────────────────────────────────────────

/** MG_MAP's keys, parsed with the SAME expression cert_component_completeness.py
 *  uses, so the two gates can never disagree about what the renderer dispatches. */
const mapKeys = (src, mapName) => {
  const m = new RegExp(
    `(?:export\\s+)?const\\s+${mapName}\\s*:[^=]*=\\s*\\{([\\s\\S]*?)\\n\\};`,
  ).exec(src);
  assert.ok(m, `${mapName} not found in PromptlyRender.tsx`);
  const body = m[1].replace(/\/\/[^\n]*/g, "");
  const out = new Map();
  for (const line of body.split("\n")) {
    for (const hit of line.matchAll(
      /(?:^|,)\s*([A-Za-z_$][\w$]*)\s*(?::\s*([\w$]+))?\s*(?=,|$)/g,
    )) {
      out.set(hit[1], hit[2] || hit[1]);
    }
  }
  return out;
};

/** A Python frozenset literal's string members. `optional` returns an empty set
 *  when the frozenset does not exist, so the render-only vocabulary below can be
 *  adopted or not without editing this gate. */
const pySet = (src, name, optional = false) => {
  const m = new RegExp(`${name}\\s*=\\s*frozenset\\(\\{([\\s\\S]*?)\\n\\}\\)`).exec(src);
  if (!m && optional) return new Set();
  assert.ok(m, `${name} not found in type_registries.py`);
  return new Set(
    [...m[1].replace(/#[^\n]*/g, "").matchAll(/"([^"]+)"/g)].map((h) => h[1]),
  );
};

/** A TS string-literal union's members. */
const tsUnion = (src, name) => {
  const m = new RegExp(`export type ${name} =([\\s\\S]*?);`).exec(src);
  assert.ok(m, `type ${name} not found in types.ts`);
  return new Set(
    [...m[1].replace(/\/\/[^\n]*/g, "").matchAll(/"([^"]+)"/g)].map((h) => h[1]),
  );
};

/** The body of a Python `def`. */
const pyFunc = (src, name) => {
  const m = new RegExp(`\\ndef ${name}\\(([\\s\\S]*?)(?=\\ndef |\\n\\n\\n|$)`).exec(src);
  assert.ok(m, `def ${name} not found in brand_components.py`);
  return m[1];
};

/** IMMEDIATE keys of the Python dict literal starting at `text[0] === "{"`.
 *
 *  CHARACTER-level depth, not line-level. `"safe": {"doctrine": ..., "x": ...}`
 *  is written on ONE line, so a line-based scan reports `doctrine`/`x`/`y` as
 *  top-level fields of the spec — a gate that fails for a reason that is not
 *  true, which is the same class as the phantom `states` field
 *  cert_component_completeness.py caught in itself. Quoted strings are consumed
 *  whole so a brace inside a string cannot move the depth. */
const immediateKeys = (text) => {
  const keys = [];
  let depth = 0, i = 0;
  while (i < text.length) {
    const c = text[i];
    if (c === '"' || c === "'") {
      let j = i + 1;
      while (j < text.length && text[j] !== c) j += text[j] === "\\" ? 2 : 1;
      const lit = text.slice(i + 1, j);
      let k = j + 1;
      while (k < text.length && /\s/.test(text[k])) k++;
      if (depth === 1 && text[k] === ":") keys.push(lit);
      i = j + 1;
      continue;
    }
    if (c === "{" || c === "[" || c === "(") depth++;
    else if (c === "}" || c === "]" || c === ")") {
      depth--;
      if (depth === 0) break;
    }
    i++;
  }
  assert.strictEqual(depth, 0, "dict literal is unbalanced");
  return new Set(keys);
};

const stripPy = (s) => s.replace(/#[^\n]*/g, "");

/** Immediate keys of the dict literal that follows `"<key>": {`. */
const dictKeys = (body, key) => {
  const src = stripPy(body);
  const at = src.indexOf(`"${key}": {`);
  assert.ok(at >= 0, `no "${key}": { ... } block found`);
  return immediateKeys(src.slice(src.indexOf("{", at)));
};

/** Immediate keys of the dict a builder RETURNS. */
const returnKeys = (body) => {
  const src = stripPy(body);
  const at = src.indexOf("return {");
  assert.ok(at >= 0, "builder has no `return {` dict");
  return immediateKeys(src.slice(src.indexOf("{", at)));
};

/** An `export const X = { ... } as const;` object literal in the adapter. */
const tsConstMap = (src, name) => {
  const m = new RegExp(`export const ${name} = \\{([\\s\\S]*?)\\} as const;`).exec(src);
  assert.ok(m, `export const ${name} not found in BrandSpecMG.tsx`);
  const out = new Map();
  for (const h of m[1].replace(/\/\/[^\n]*/g, "").matchAll(/([a-z_]+)\s*:\s*"([^"]+)"/g)) {
    out.set(h[1], h[2]);
  }
  return out;
};

const sorted = (s) => [...s].sort();
const diff = (a, b) => sorted([...a].filter((x) => !b.has(x)));

const MG_MAP = mapKeys(RENDER, "MG_MAP");
// THE RENDERABLE MG VOCABULARY = what the model may author, PLUS any render-
// input-only types the pipeline appends itself. The second set is optional and
// mirrors the existing `HardHold` precedent in render_schemas.py: a type the
// renderer must accept and Gemini must never be able to emit. Whether the
// spec-built components live in one set or the other is the lead's call — this
// gate only insists the renderer and the schema agree on the UNION.
const VALID_MG = new Set([
  ...pySet(REGISTRY_PY, "VALID_MG_TYPES"),
  ...pySet(REGISTRY_PY, "VALID_RENDER_ONLY_MG_TYPES", true),
]);
const TS_MG = tsUnion(TYPES_TS, "MotionGraphicType");
const NP_BODY = pyFunc(BRAND_PY, "build_name_plate");
const EC_BODY = pyFunc(BRAND_PY, "build_end_card");

// The two spec-built components, DERIVED from the producer names exactly the way
// cert_component_completeness.producer_component_name does it (build_name_plate
// -> NamePlate), so this gate cannot gate a different set than that one.
const SPEC_COMPONENTS = [...BRAND_PY.matchAll(/^def build_(\w+)\(/gm)]
  .map((h) => h[1])
  .filter((s) => s !== "brand_specs")
  .map((s) => s.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join(""));

// ── 1. DISPATCH: the link that produces pixels ──────────────────────────────
check("every spec-built component is a KEY in MG_MAP (the pixel link)", () => {
  const missing = SPEC_COMPONENTS.filter((c) => !MG_MAP.has(c));
  assert.strictEqual(
    missing.length, 0,
    `${JSON.stringify(missing)} have a brand_components producer and a Remotion `
    + `component but NO MG_MAP key — MotionGraphicRenderer looks the type up in `
    + `MG_MAP and returns null on a miss, so requesting them moves a counter, `
    + `NOT pixels. MG_MAP currently dispatches: ${JSON.stringify(sorted(MG_MAP.keys()))}`,
  );
});

check("MG_MAP dispatches the spec ADAPTERS, never the bare components", () => {
  // The bare components take `name` / `title` + `palette`; the spec carries
  // `name` nested under a different shape, `headline`, and `style`. Registering
  // the bare component compiles, renders, and draws NOTHING readable.
  for (const c of SPEC_COMPONENTS) {
    if (!MG_MAP.has(c)) continue; // reported by the check above
    assert.strictEqual(
      MG_MAP.get(c), `${c}MG`,
      `MG_MAP["${c}"] dispatches ${MG_MAP.get(c)}; it must dispatch the adapter `
      + `${c}MG from motion-graphics/brand, which maps the brand_components spec `
      + `dict onto the component's props`,
    );
  }
  assert.ok(
    /import \{[^}]*NamePlateMG[^}]*EndCardMG[^}]*\} from "\.\/motion-graphics\/brand"/s
      .test(RENDER),
    "PromptlyRender.tsx does not import the adapters from ./motion-graphics/brand",
  );
});

// ── 2. THE THREE MIRRORS AGREE ──────────────────────────────────────────────
check("MG_MAP === type_registries.VALID_MG_TYPES (both directions)", () => {
  const unrequestable = diff(new Set(MG_MAP.keys()), VALID_MG);
  const unrenderable = diff(VALID_MG, new Set(MG_MAP.keys()));
  assert.strictEqual(
    unrequestable.length, 0,
    `the renderer can dispatch ${JSON.stringify(unrequestable)} but `
    + `type_registries.VALID_MG_TYPES has no member for it, so handler's _MG_TYPES `
    + `Literal and render_schemas.MotionGraphicType both REJECT it — the model can `
    + `never emit it and the render input cannot carry it. Add it to VALID_MG_TYPES.`,
  );
  assert.strictEqual(
    unrenderable.length, 0,
    `VALID_MG_TYPES lets the model emit ${JSON.stringify(unrenderable)} but MG_MAP `
    + `has no component — MotionGraphicRenderer returns null and the MG silently `
    + `never appears`,
  );
});

check("src/types.ts MotionGraphicType === VALID_MG_TYPES (the third mirror)", () => {
  const a = diff(VALID_MG, TS_MG), b = diff(TS_MG, VALID_MG);
  assert.strictEqual(
    a.length + b.length, 0,
    `types.ts is the mirror that silently blocked motionTokens once already. `
    + `Missing from types.ts: ${JSON.stringify(a)}; extra in types.ts: ${JSON.stringify(b)}`,
  );
});

// ── 3. THE ADAPTER SPENDS EVERY STYLE FIELD ─────────────────────────────────
const STYLE_CASES = [
  ["name_plate", NP_BODY, "NAME_PLATE_STYLE_MAP", NAMEPLATE_T],
  ["end_card", EC_BODY, "END_CARD_STYLE_MAP", ENDCARD_T],
];

for (const [label, body, mapName, componentTypes] of STYLE_CASES) {
  const specStyle = dictKeys(body, "style");
  const map = tsConstMap(ADAPTER, mapName);

  check(`${label}: every style field the producer emits is MAPPED (${specStyle.size})`, () => {
    const dropped = diff(specStyle, new Set(map.keys()));
    const phantom = diff(new Set(map.keys()), specStyle);
    assert.strictEqual(
      dropped.length, 0,
      `brand_components emits style.${dropped.join(", style.")} and ${mapName} `
      + `maps ${JSON.stringify(sorted(map.keys()))} — a dropped style field is a `
      + `component rendering in a size or colour the design system did not choose`,
    );
    assert.strictEqual(
      phantom.length, 0,
      `${mapName} maps ${JSON.stringify(phantom)}, which brand_components does not `
      + `emit — the map is describing a shape that no longer exists`,
    );
  });

  check(`${label}: every mapped field is actually READ and PASSED in the adapter`, () => {
    for (const [specKey, prop] of map) {
      assert.ok(
        ADAPTER.includes(`style.${specKey}`),
        `${mapName} claims style.${specKey} -> ${prop}, but BrandSpecMG.tsx never `
        + `dereferences style.${specKey} — the map is a comment, not wiring`,
      );
      if (prop.includes(".")) {
        // e.g. "palette.bg": the prop is one member of an object prop literal.
        const [obj, member] = prop.split(".");
        assert.ok(
          new RegExp(`${obj}=\\{\\{[^}]*${member}\\s*:`, "s").test(ADAPTER),
          `${mapName} maps style.${specKey} -> ${prop}, but the adapter never `
          + `assigns ${member} inside the ${obj}={{ ... }} prop`,
        );
        assert.ok(
          new RegExp(`${obj}\\s*:\\s*\\{[^}]*${member}\\s*:`, "s").test(componentTypes),
          `${prop} is not declared on the component's props`,
        );
      } else {
        assert.ok(
          new RegExp(`\\b${prop}=\\{`).test(ADAPTER),
          `${mapName} maps style.${specKey} -> ${prop}, but the adapter never `
          + `passes a ${prop}={...} prop`,
        );
        assert.ok(
          new RegExp(`\\b${prop}\\??\\s*:`).test(componentTypes),
          `prop ${prop} is not declared in the component's types.ts — TypeScript `
          + `would reject the adapter, or worse, the prop would be silently ignored`,
        );
      }
    }
  });
}

// ── 4. NO TOP-LEVEL SPEC FIELD IS LOST IN SILENCE ───────────────────────────
// A field the adapter does not read must be OWNED by someone, on purpose. These
// are the four the HANDLER spends: `start_s`/`hold_s` become fromFrame/
// durationInFrames on the Sequence, `kind` selects which MG type is appended,
// and `source` is provenance for the liveness counter. Everything else must
// reach a prop, or this check names it.
const HANDLER_OWNED = new Set(["kind", "start_s", "hold_s", "source"]);
for (const [label, body] of [["name_plate", NP_BODY], ["end_card", EC_BODY]]) {
  check(`${label}: every top-level spec field is read by the adapter or handler-owned`, () => {
    const keys = returnKeys(body);
    assert.ok(keys.size >= 6, `only parsed ${sorted(keys)} out of ${label} — the parser broke`);
    const lost = sorted(keys).filter(
      (k) => !HANDLER_OWNED.has(k) && !ADAPTER.includes(`spec.${k}`),
    );
    assert.strictEqual(
      lost.length, 0,
      `brand_components emits ${JSON.stringify(lost)} on the ${label} spec and the `
      + `adapter never reads spec.<field>. Either wire it to a prop or add it to `
      + `HANDLER_OWNED with the reason — a field nobody spends is a field the `
      + `design system computed for nothing`,
    );
  });
}

// ── 5. THE MOUNT CANNOT CRASH THE RENDER ────────────────────────────────────
check("NamePlate/EndCard call useMGPhase with its REQUIRED defaults object", () => {
  // Shipped for days with a single argument. useMGPhase destructures its second
  // parameter, so `useMGPhase(timing)` is `TypeError: Cannot destructure property
  // 'defaultEnterFrames' of 'undefined'` AT MOUNT — the first job that ever
  // requested a name-plate would have lost its whole video to a component crash.
  for (const [name, src] of [["NamePlate", NAMEPLATE], ["EndCard", ENDCARD]]) {
    const call = /useMGPhase\(([\s\S]*?)\n\s*\);/.exec(src);
    assert.ok(call, `${name} does not call useMGPhase`);
    assert.ok(
      call[1].includes("defaultEnterFrames") && call[1].includes("defaultExitFrames"),
      `${name} calls useMGPhase without the { defaultEnterFrames, defaultExitFrames } `
      + `argument — that is a TypeError at mount, i.e. RENDER_FATAL for the job`,
    );
  }
});

check("both components fail CLOSED on missing copy (no plate/card without words)", () => {
  assert.ok(
    /const name = str\(spec\.name\);\s*\n\s*if \(!name\) return null;/.test(ADAPTER),
    "NamePlateMG must return null without a name — a coloured rule means nothing",
  );
  assert.ok(
    /const headline = str\(spec\.headline\);\s*\n\s*if \(!headline\) return null;/.test(ADAPTER),
    "EndCardMG must return null without a headline",
  );
  assert.ok(
    /if \(!field \|\| !ink \|\| !rule\) return null;/.test(ADAPTER),
    "EndCardMG must return null on a partial palette — a defaulted colour on the "
    + "close is an INVENTED BRAND owning 100% of the pixels",
  );
});

// ── 6. THE DISPATCH CONTRACT THE ADAPTER DEPENDS ON ─────────────────────────
check("MotionGraphicRenderer still supplies startMs=0 + window durationMs + spread props", () => {
  const m = /const Comp = MG_MAP\[spec\.type\];([\s\S]*?)\n\};/.exec(RENDER);
  assert.ok(m, "MotionGraphicRenderer not found");
  assert.ok(/startMs=\{0\}/.test(m[1]), "startMs is no longer pinned to 0");
  assert.ok(
    /durationMs=\{Math\.round\(\(spec\.durationInFrames \/ fps\) \* 1000\)\}/.test(m[1]),
    "durationMs no longer derives from the Sequence window — the adapters assume "
    + "the handler owns placement (fromFrame/durationInFrames) and the component "
    + "owns only its entrance/exit inside that window",
  );
  assert.ok(/\{\.\.\.spec\.props\}/.test(m[1]), "spec.props is no longer spread onto the component");
  assert.ok(
    /<Sequence[\s\S]*?from=\{mg\.fromFrame\}[\s\S]*?durationInFrames=\{mg\.durationInFrames\}/
      .test(RENDER),
    "the MG <Sequence> no longer takes its window from fromFrame/durationInFrames",
  );
});

// ── 7. INVENTORY HYGIENE ────────────────────────────────────────────────────
check("the adapters are NOT re-exported from the motion-graphics barrel", () => {
  // cert_component_completeness.py reports every uppercase barrel export that is
  // in no dispatch map as dead code. The adapters are dispatch wrappers, not
  // components; exporting them there would print two permanent false orphans.
  for (const n of ["NamePlateMG", "EndCardMG"]) {
    assert.ok(!BARREL.includes(n), `${n} is exported from motion-graphics/index.ts`);
  }
});

console.log(
  `\n${passed} checks passed${process.exitCode ? " — WITH FAILURES" : ""}\n`,
);
