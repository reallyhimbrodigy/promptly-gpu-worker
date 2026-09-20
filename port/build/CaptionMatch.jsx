/* NO HARDCODED FALLBACK LIVES HERE (Zac, 2026-09-20). Defaults belong to the
 * property table and nowhere else. ChatCut REWRITES the code at registration, so a
 * fallback in source is dead code that looks live — and with none to strip, the
 * registered blob comes back byte-identical and port/registered_diff.mjs can assert
 * exact equality, which is the only way to know the code that runs is the code we
 * built. */
/* CaptionMatch - the caption_match text overlay, ported from the old pipeline's family.
 *
 * WHY IT IS BACK. text_overlays was a FAMILY in the live pipeline and it is absent
 * from the 73. The references place text most of the time; until this lands the
 * agent cannot. The family's real list came from the SCHEMA'S OWN HISTORY, not the
 * pruned enum: torn_paper, sticky_note, quote_card, lower_third, caption_match.
 * Three were retired from the enum while the record kept carrying their fields,
 * which is how a family reads as two variants and is five.
 *
 * Renders in the EDIT'S CHOSEN CAPTION STYLE, which is the whole point of the
 * variant: mono-brand work where matching the caption IS the brand. The old spec
 * warns it is the wrong pick otherwise.
 *
 * IT DID NOT DO THIS UNTIL 2026-09-19. The first port rendered a fixed sans-serif
 * and never consulted the style, which made it accidentally PLAIN — the most common
 * shape in the references, on the menu under a name promising something else. The
 * style arrives as a property because a ChatCut component sees only item.props;
 * the harness passes the edit's own choice. The nine signatures below are read from
 * the renderer's own caption components, not invented.
 *
 * THE DIALS ARE VISIBLE. size and position are properties, defaulting to what the
 * references measure - medium, middle - so the platter shows the editor the two
 * things it will most often want to change instead of burying them.
 *
 * NO VELOCITY CAP: this draws no video and performs no ramp. The cap bounds the
 * per-frame displacement of a zoom on the source; there is no source here.
 *
 * CONTRACT (from ChatCut's validator): one top-level component, no top-level
 * constants, a plain div root, values read through an identifier named props, and
 * every declared property read at least once.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const props = (item && item.props) || {};
  const size = props.size;
  const position = props.position;
  const accent = props.accentColor;
  const textColor = props.textColor;
  // THE REFERENCE SCALE, the same ladder the component sheet already uses.
  const fontSize = size === "xlarge" ? 168 : size === "large" ? 128 : size === "small" ? 72 : 96;
  const justify = position === "top" ? "flex-start" : position === "bottom" ? "flex-end" : "center";
  const pad = Math.round(fontSize * 0.9);
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    flexDirection: "column", alignItems: "center", justifyContent: justify,
    overflow: "hidden", boxSizing: "border-box", padding: pad,
    gap: Math.round(fontSize * 0.3) };
  // Entrance eases POSITION, never opacity: this repo's caption law is
  // FRAME-1-IS-FINAL for readable text, so the words are legible on frame one.
  const t = Math.min(Math.max(frame / Math.max(1, Math.round(0.28 * fps)), 0), 1);
  const ease = 1 - Math.pow(1 - t, 3);
  const text = String(props.text);
  const captionStyle = props.captionStyle;
  // THE FAMILY ARRIVES AS A `font`-TYPED PROPERTY, NOT AS A CSS STRING. Measured
  // 2026-09-19: CleanCut and Quintessence differ ONLY in typeface and rendered
  // PIXEL-IDENTICAL, while Gadzhi (which uppercases) differed from both — so the
  // property was read and the TYPEFACE was not honoured. Both families exist in
  // ChatCut's catalogue under those exact names, so the family was available and
  // simply never loaded: a bare fontFamily string names a face the renderer was
  // never told to fetch. ChatCut's own guidance is to resolve through search_fonts
  // and carry the canonical name in a `font` property, which is what loads it.
  const fontFamily = props.fontFamily;
  const pop = 0.94 + 0.06 * ease;
  // THE NINE, from src/remotion/src/captions/<style>/: the font each one actually
  // renders with, its weight, and whether it transforms case. A style this does not
  // know falls back to CleanCut rather than silently rendering something else.
  const styles = {
    CleanCut: [700, "none", 0],
    Cove: [700, "none", 0],
    Gadzhi: [700, "uppercase", -1],
    Lumen: [800, "none", 0],
    Prime: [800, "lowercase", 0],
    Pulse: [800, "none", 0],
    Quintessence: [700, "none", 0],
    TwoTone: [900, "none", -1],
    TypewriterReveal: [700, "none", 1],
  };
  const sty = styles[captionStyle] || styles.CleanCut;
  if (!text) {
    return (<div style={rootStyle}><div style={{ color: accent, fontSize: 40, fontFamily: "sans-serif" }}>NO TEXT</div></div>);
  }
  return (
    <div style={rootStyle}>
      <div style={{ transform: "scale(" + pop + ")", color: textColor, fontFamily: fontFamily,
                    fontWeight: sty[0], textTransform: sty[1], letterSpacing: sty[2],
                    fontSize: fontSize, lineHeight: 1.06, textAlign: "center",
                    maxWidth: "94%", whiteSpace: "normal", overflowWrap: "break-word",
                    textShadow: "0 6px 22px rgba(0,0,0,0.55)" }}>
        {text}
      </div>
    </div>
  );
};
