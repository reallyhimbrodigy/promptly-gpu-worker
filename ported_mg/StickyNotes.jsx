// ── ported prelude: injected globals re-bound ──
const createElement = React.createElement;

// src/motion-graphics/StickyNotes/StickyNotes.tsx
// [ported] import removed — ChatCut injects these: remotion
// gfont:@remotion/google-fonts/Inter
var loadFont = () => ({ fontFamily: "Inter" });

// gfont:@remotion/google-fonts/Anton
var loadFont2 = () => ({ fontFamily: "Anton" });

// gfont:@remotion/google-fonts/DMSerifDisplay
var loadFont3 = () => ({ fontFamily: "DMSerifDisplay" });

// gfont:@remotion/google-fonts/PlayfairDisplay
var loadFont4 = () => ({ fontFamily: "PlayfairDisplay" });

// gfont:@remotion/google-fonts/CaveatBrush
var loadFont5 = () => ({ fontFamily: "CaveatBrush" });

// gfont:@remotion/google-fonts/Oswald
var loadFont6 = () => ({ fontFamily: "Oswald" });

// gfont:@remotion/google-fonts/Roboto
var loadFont7 = () => ({ fontFamily: "Roboto" });

// gfont:@remotion/google-fonts/JetBrainsMono
var loadFont8 = () => ({ fontFamily: "JetBrainsMono" });

// gfont:@remotion/google-fonts/NotoSansDevanagari
var loadFont9 = () => ({ fontFamily: "NotoSansDevanagari" });

// gfont:@remotion/google-fonts/NotoSansBengali
var loadFont10 = () => ({ fontFamily: "NotoSansBengali" });

// gfont:@remotion/google-fonts/NotoSansTelugu
var loadFont11 = () => ({ fontFamily: "NotoSansTelugu" });

// gfont:@remotion/google-fonts/NotoSansArabic
var loadFont12 = () => ({ fontFamily: "NotoSansArabic" });

// src/motion-graphics/shared/fonts.ts
var SUBSETS = ["latin", "latin-ext"];
var inter = loadFont("normal", { weights: ["400", "500", "600", "700", "800", "900"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
var anton = loadFont2("normal", { weights: ["400"], subsets: [...SUBSETS] });
var dmSerifDisplay = loadFont3("normal", { weights: ["400"], subsets: [...SUBSETS] });
var playfairDisplay = loadFont4("normal", { weights: ["400", "700"], subsets: [...SUBSETS] });
var caveatBrush = loadFont5("normal", { weights: ["400"], subsets: [...SUBSETS] });
var oswald = loadFont6("normal", { weights: ["400", "600", "700"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
var roboto = loadFont7("normal", { weights: ["400", "500", "700"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
var jetBrainsMono = loadFont8("normal", { weights: ["400", "500", "700"], subsets: [...SUBSETS] });
var notoSansDevanagari = loadFont9("normal", { weights: ["400", "700"], subsets: ["devanagari", "latin"] });
var notoSansBengali = loadFont10("normal", { weights: ["400", "700"], subsets: ["bengali", "latin"] });
var notoSansTelugu = loadFont11("normal", { weights: ["400", "700"], subsets: ["telugu", "latin"] });
var notoSansArabic = loadFont12("normal", { weights: ["400", "700"], subsets: ["arabic"] });
var MG_FONTS = {
  inter: inter.fontFamily,
  anton: anton.fontFamily,
  dmSerifDisplay: dmSerifDisplay.fontFamily,
  playfairDisplay: playfairDisplay.fontFamily,
  caveatBrush: caveatBrush.fontFamily,
  oswald: oswald.fontFamily,
  roboto: roboto.fontFamily,
  jetBrainsMono: jetBrainsMono.fontFamily,
  notoSansDevanagari: notoSansDevanagari.fontFamily,
  notoSansBengali: notoSansBengali.fontFamily,
  notoSansTelugu: notoSansTelugu.fontFamily,
  notoSansArabic: notoSansArabic.fontFamily
};

// src/motion-graphics/shared/text-script.ts
var RANGES = [
  ["devanagari", /[ऀ-ॿ]/],
  ["bengali", /[ঀ-৿]/],
  ["telugu", /[ఀ-౿]/],
  ["arabic", /[؀-ۿݐ-ݿ]/],
  ["cyrillic", /[Ѐ-ӿ]/],
  ["cjk", /[一-鿿぀-ヿ가-힯]/]
];
function detectScript(text) {
  for (const [script, re] of RANGES) {
    if (re.test(text)) return script;
  }
  return "latin";
}
var CYRILLIC_CAPABLE = /* @__PURE__ */ new Set(["inter", "oswald", "roboto"]);
var SCRIPT_FACE_KEY = {
  devanagari: "notoSansDevanagari",
  bengali: "notoSansBengali",
  telugu: "notoSansTelugu",
  arabic: "notoSansArabic"
};
function routeFaceKey(text, preferredKey) {
  const script = detectScript(text);
  if (script === "cyrillic" && !CYRILLIC_CAPABLE.has(preferredKey)) {
    return "oswald";
  }
  return SCRIPT_FACE_KEY[script] ?? preferredKey;
}
function mgTextMetrics(text) {
  const script = detectScript(text);
  const nonLatin = script !== "latin";
  return {
    script,
    lineHeight: nonLatin ? 1.3 : 1,
    uppercaseSafe: !nonLatin,
    advanceEm: script === "latin" ? 0.62 : 0.42
  };
}

// src/motion-graphics/shared/text-font.ts
var EMOJI_TAIL = "'Noto Color Emoji', sans-serif";
function mgTextFont(text, preferred = "inter") {
  const key = routeFaceKey(text, preferred);
  const base = MG_FONTS[key] ?? MG_FONTS[preferred];
  return `${base}, ${EMOJI_TAIL}`;
}

// src/motion-graphics/shared/timing.ts
function msToFrames(ms, fps) {
  return Math.round(ms / 1e3 * fps);
}

// src/shared/safeZone.ts
var CANVAS_WIDTH = 1080;
var CANVAS_HEIGHT = 1920;
var TIKTOK_SAFE_TOP = 270;
var TIKTOK_SAFE_RIGHT = 200;
var TIKTOK_SAFE_BOTTOM = 420;
var TIKTOK_SAFE_SIDE = 80;
var SAFE_RECT = {
  x: TIKTOK_SAFE_SIDE,
  // 80
  y: TIKTOK_SAFE_TOP,
  // 270
  width: CANVAS_WIDTH - TIKTOK_SAFE_SIDE - TIKTOK_SAFE_RIGHT,
  // 800
  height: CANVAS_HEIGHT - TIKTOK_SAFE_TOP - TIKTOK_SAFE_BOTTOM
  // 1230
};

// src/captions/shared/fit.ts
var H_TEXT_MARGIN = TIKTOK_SAFE_SIDE;
var SAFE_TEXT_WIDTH = CANVAS_WIDTH - 2 * H_TEXT_MARGIN;
var _ctx;
var _measureCache = /* @__PURE__ */ new Map();
function getCtx() {
  if (_ctx !== undefined) return _ctx;
  try {
    const canvas = document.createElement("canvas");
    _ctx = canvas.getContext("2d");
  } catch {
    _ctx = null;
  }
  return _ctx;
}
var canvasMeasurer = (word, fontSize, font) => {
  const text = font.uppercase ? word.toUpperCase() : font.lowercase ? word.toLowerCase() : word;
  const spacingPx = (font.letterSpacingEm ?? 0) * fontSize;
  const key = `${font.fontFamily}|${font.fontWeight}|${fontSize}|${spacingPx}|${text}`;
  const hit = _measureCache.get(key);
  if (hit !== undefined) return hit;
  const ctx = getCtx();
  if (!ctx) return text.length * fontSize * 0.62 + spacingPx * text.length;
  ctx.font = `${font.fontWeight} ${fontSize}px ${font.fontFamily}`;
  const anyCtx = ctx;
  let width;
  if ("letterSpacing" in anyCtx) {
    anyCtx.letterSpacing = `${spacingPx}px`;
    width = ctx.measureText(text).width;
  } else {
    width = ctx.measureText(text).width + spacingPx * text.length;
  }
  _measureCache.set(key, width);
  return width;
};
var _graphemeSeg = typeof Intl !== "undefined" && Intl.Segmenter ? new Intl.Segmenter(undefined, { granularity: "grapheme" }) : null;
var CHARWRAP_FALLBACK_STYLE = {
  whiteSpace: "normal",
  overflowWrap: "anywhere",
  wordBreak: "break-word"
};

// src/shared/asText.ts
var asText = (v) => typeof v === "string" ? v : v == null ? "" : String(v);

// src/motion-graphics/StickyNotes/StickyNotes.tsx
var STICKY_FIT_FLOOR = 0.35;
// 1.0, WAS 2.6 — THE FIT MAY SHRINK AND MUST NEVER GROW (2026-09-23).
//
// MEASURED, not reasoned: at 2.6 a 15-character word fits its paper with
// margin while a 5-character word and even a 2-character word run past both
// edges. The shrink search is correct; the UPSCALE is what overflows, and the
// shorter the word the larger the scale it is given and the worse it gets.
//
// WHY UPSCALING OVERFLOWS AT ALL. canvasMeasurer returns measureText().width,
// which is the ADVANCE width — the pen travel — not the INK box. Caveat Brush
// is a brush script whose strokes overhang their advances, so the ink is wider
// than the number the fit is checking, by an amount proportional to font size.
// At scale 1 that overhang is a few pixels inside a 272px paper; at 2.6 it is
// the difference between fitting and hanging off the edge.
//
// THIS IS THE LOAD-BEARING HALF OF THE sqrt RULE CaptionMatch USES:
// `Math.min(1, sqrt(REF/len))` — it clamps at 1 and only ever shrinks. A fit
// that can grow is a fit that can exceed the box it was measured against on
// the SHORTEST content, which is the opposite of where anyone looks for it.
//
// Measuring the ink box (actualBoundingBoxLeft/Right) would fix it at the root
// and is the better long-term answer, but canvasMeasurer is SHARED with other
// components and this failure only appears on upscale. Removing the upscale
// removes the failure with no blast radius.
var STICKY_FIT_CEIL = 1.0;
function fitStickyNote(text, noteFontSize, fontFamily, noteSize, lineHeightEm = 1.1) {
  const font = { fontFamily, fontWeight: 400 };
  const inner = noteSize - 20 - 8;
  const vBudget = inner - 30;
  const words = asText(text).split(/\s+/).filter(Boolean);
  if (words.length === 0) return { scale: 1, floored: false };
  for (let s = STICKY_FIT_CEIL; s >= STICKY_FIT_FLOOR - 1e-6; s -= 0.05) {
    const size = noteFontSize * s;
    const widths = words.map((w2) => canvasMeasurer(w2, size, font));
    if (Math.max(...widths) > inner) continue;
    const spacePx = canvasMeasurer(" ", size, font);
    let lines = 1;
    let w = 0;
    for (const ww of widths) {
      const extra = w > 0 ? spacePx + ww : ww;
      if (w > 0 && w + extra > inner) {
        lines++;
        w = ww;
      } else {
        w += extra;
      }
    }
    if (lines * size * lineHeightEm <= vBudget) {
      if (s < 1 - 1e-6) {
        console.log(
          `[caption-fit] style=StickyNotes page="${text}" action=scale(${s.toFixed(2)})`
        );
      }
      return { scale: s, floored: false };
    }
  }
  console.log(
    `[caption-fit] style=StickyNotes page="${text}" action=charwrap`
  );
  return { scale: STICKY_FIT_FLOOR, floored: true };
}
var NOTE_POSITIONS = [
  [-310, 20],
  [0, -30],
  [305, 15]
];
var StickyNotes = ({
  startMs,
  durationMs,
  notes,
  noteSize = 300,
  noteFontSize = 50,
  noteFontFamily = MG_FONTS.caveatBrush,
  // FOG OFF BY DEFAULT (2026-09-23). It paints a full-width band over the top
  // half of the box starting at rgba(255,255,255,1) — FULLY OPAQUE WHITE — and
  // in ChatCut's export that is a solid white band across the frame, not
  // atmosphere. Same family as SectionDivider's scrim and vignette and
  // Reticle's window plane: a decorative layer whose failure mode is an opaque
  // rectangle over the user's video.
  showFog = false,
  topOffset = "5%"
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = fps / 60;
  const appearFrame = msToFrames(startMs, fps);
  const disappearFrame = msToFrames(startMs + durationMs, fps);
  if (frame < appearFrame - 10 * s) return null;
  if (frame > disappearFrame + 10 * s) return null;
  const elapsed = frame - appearFrame;
  const fogOpacity = interpolate(elapsed, [-5 * s, 10 * s], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp"
  });
  const fogFadeOut = interpolate(
    frame,
    [disappearFrame, disappearFrame + 10 * s],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const fogOverall = Math.min(fogOpacity, fogFadeOut);
  const renderableNotes = notes.slice(0, 3);
  return <AbsoluteFill>
      {showFog ? <div
    style={{
      opacity: fogOverall,
      position: "absolute",
      top: 0,
      left: 0,
      width: "100%",
      height: "50%",
      background: "linear-gradient(to bottom, rgba(255,255,255,1) 0%, rgba(255,255,255,0.85) 30%, rgba(255,255,255,0.4) 60%, transparent 100%)"
    }}
  /> : null}

      <div
    style={{
      position: "absolute",
      top: topOffset,
      left: "50%",
      transform: "translateX(-50%)",
      width: noteSize * 3 + 60,
      height: noteSize + 80
    }}
  >
        {renderableNotes.map((note, i) => {
    const noteDelay = 5 * i * s;
    const noteElapsed = elapsed - noteDelay - 2 * s;
    const oscT = noteElapsed * (60 / fps);
    const swayFreq = [0.35, 0.28, 0.32][i] ?? 0.3;
    const swayDir = i === 1 ? -1 : 1;
    const fallProgress = spring({
      fps,
      frame: noteElapsed,
      config: {
        mass: 0.6,
        damping: 14,
        stiffness: 160,
        overshootClamping: false
      }
    });
    const enterY = interpolate(fallProgress, [0, 1], [-350, 0]);
    const swayAmount = interpolate(
      fallProgress,
      [0, 0.3, 0.6, 1],
      [0, 1, 0.5, 0]
    );
    const swayX = Math.sin(oscT * swayFreq) * 45 * swayAmount * swayDir;
    const rockAmount = interpolate(
      fallProgress,
      [0, 0.3, 0.7, 1],
      [0, 1, 0.4, 0]
    );
    const rockAngle = Math.sin(oscT * swayFreq + 0.5) * 18 * rockAmount;
    const enterRotation = note.rotation + rockAngle;
    const tiltAmount = interpolate(
      fallProgress,
      [0, 0.4, 0.8, 1],
      [0, 1, 0.3, 0]
    );
    const tiltX = Math.sin(oscT * swayFreq * 1.3) * 25 * tiltAmount;
    const tiltY = Math.cos(oscT * swayFreq * 0.9) * 15 * tiltAmount;
    const enterScale = interpolate(
      fallProgress,
      [0, 0.5, 1],
      [1.15, 1.03, 1]
    );
    const enterOpacity = interpolate(fallProgress, [0, 0.12], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp"
    });
    const enterShadowBlur = interpolate(fallProgress, [0, 1], [35, 6]);
    const enterShadowY = interpolate(fallProgress, [0, 1], [25, 3]);
    const enterShadowOp = interpolate(
      fallProgress,
      [0, 1],
      [0.06, 0.2]
    );
    const exitDelay = (2 - i) * 3 * s;
    const exitElapsed = frame - disappearFrame + exitDelay;
    const isExiting = exitElapsed >= 0;
    const exitProgress = spring({
      fps,
      frame: Math.max(0, exitElapsed),
      config: {
        mass: 0.4,
        damping: 16,
        stiffness: 200,
        overshootClamping: true
      }
    });
    const windAngles = [-35, 10, 40];
    const windAngle = (windAngles[i] ?? 0) * (Math.PI / 180);
    const windDist = interpolate(exitProgress, [0, 1], [0, 500]);
    const exitX = Math.sin(windAngle) * windDist;
    const exitY = -Math.cos(windAngle) * windDist;
    const exitSpin = interpolate(
      exitProgress,
      [0, 1],
      [0, (i === 1 ? -1 : 1) * 45]
    );
    const exitTiltX = interpolate(exitProgress, [0, 1], [0, 30]);
    const exitTiltY = interpolate(
      exitProgress,
      [0, 1],
      [0, (i === 0 ? -1 : 1) * 25]
    );
    const exitScale = interpolate(exitProgress, [0, 1], [1, 0.6]);
    const exitOpacity = interpolate(
      exitProgress,
      [0, 0.5, 1],
      [1, 0.7, 0]
    );
    const finalX = isExiting ? exitX : swayX;
    const finalY = isExiting ? exitY : enterY;
    const finalRot = isExiting ? note.rotation + exitSpin : enterRotation;
    const finalTiltX = isExiting ? exitTiltX : tiltX;
    const finalTiltY = isExiting ? exitTiltY : tiltY;
    const finalScale = isExiting ? exitScale : enterScale;
    const finalOpacity = isExiting ? exitOpacity : enterOpacity;
    const finalShadowBlur = isExiting ? interpolate(exitProgress, [0, 1], [6, 30]) : enterShadowBlur;
    const finalShadowY = isExiting ? interpolate(exitProgress, [0, 1], [3, 20]) : enterShadowY;
    const finalShadowOp = isExiting ? interpolate(exitProgress, [0, 1], [0.2, 0.03]) : enterShadowOp;
    const posScale = noteSize / 300;
    const [baseX, baseY] = NOTE_POSITIONS[i] ?? [0, 0];
    const xOff = baseX * posScale;
    const yOff = baseY * posScale;
    const noteFace = mgTextFont(note.text, "caveatBrush");
    const noteLineHeight = Math.max(
      1.1,
      mgTextMetrics(note.text).lineHeight
    );
    const noteFit = fitStickyNote(
      note.text,
      noteFontSize,
      noteFace,
      noteSize,
      noteLineHeight
    );
    return <div
      key={i}
      style={{
        position: "absolute",
        left: "50%",
        top: "50%",
        width: noteSize,
        height: noteSize,
        marginLeft: xOff - noteSize / 2,
        marginTop: yOff - noteSize / 2,
        zIndex: i,
        perspective: 800
      }}
    >
              <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: note.color,
        transform: `translate(${finalX}px, ${finalY}px) rotateX(${finalTiltX}deg) rotateY(${finalTiltY}deg) rotate(${finalRot}deg) scale(${finalScale})`,
        transformOrigin: "center center",
        opacity: finalOpacity,
        boxShadow: `2px ${finalShadowY}px ${finalShadowBlur}px rgba(0,0,0,${finalShadowOp})`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 10
      }}
    >
                {i === 0 ? (
      // Drawn check, not a glyph (pass #12, audited): U+2713 does
      // not exist in Caveat Brush — the ✓ silently rendered in a
      // fallback face. An inline SVG has no font dependency and
      // keeps the hand-drawn register.
      <svg
        width={noteFontSize * 0.8}
        height={noteFontSize * 0.62}
        viewBox="0 0 40 31"
        style={{ marginBottom: 2 }}
      >
                    <path
        d="M3 17 C9 22 13 26 15 28 C21 18 30 8 37 3"
        fill="none"
        stroke="#1A1A1A"
        strokeWidth={4.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
                  </svg>
    ) : null}

                <span
      style={{
        fontFamily: noteFace,
        fontSize: noteFontSize * noteFit.scale,
        fontWeight: 400,
        color: "#1A1A1A",
        textAlign: "center",
        lineHeight: noteLineHeight,
        // ITALIC DROPPED FROM SLOT 3 (2026-09-23). A 5-character word ran
        // past its paper's right edge while the same 5 characters fitted
        // upright in slot 1, and the fit is already per-note — so the note
        // was measured correctly and drawn wider than it was measured.
        //
        // WHY NO MEASURER CHANGE FIXES IT. caveatBrush is loaded
        // `loadFont("normal", { weights: ["400"] })` — there is NO italic cut,
        // so `fontStyle: italic` is SYNTHETIC OBLIQUE. Synthetic oblique keeps
        // the ADVANCE WIDTHS identical and SHEARS the glyphs, so the ink
        // escapes the advance box the measurer measured. Telling the measurer
        // the style would return the same number; the fit would shrink
        // nothing; the word would still overhang. The mismatch is not in the
        // measurement, it is between an advance box and the ink inside it.
        //
        // And it was redundant: caveatBrush is already a casual brush script,
        // so the slant was a synthetic slope on a face that has its own.
        fontStyle: "normal",
        maxWidth: "100%",
        ...noteFit.floored ? CHARWRAP_FALLBACK_STYLE : {}
      }}
    >
                  {note.text}
                </span>

                {i === 2 ? <div
      style={{
        width: "60%",
        height: 2,
        backgroundColor: "#1A1A1A",
        marginTop: 4,
        borderRadius: 2,
        opacity: 0.5
      }}
    /> : null}
              </div>
            </div>;
  })}
      </div>
    </AbsoluteFill>;
};


// ── ChatCut adapter (generated) ──────────────────────────────────────────────
// Root must be a plain div per the MG contract; AbsoluteFill may only be an
// inner layer. Editable values arrive on item.props.
const Component = ({ item }) => {
  const rootStyle = { position: "absolute", inset: 0, backgroundColor: "transparent" };
  const p = (item && item.props) || {};
  return <div style={rootStyle}><StickyNotes {...p} /></div>;
};
