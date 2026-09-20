/* TornPaper - the torn_paper text overlay, ported from the old pipeline's family.
 *
 * WHY IT IS BACK. text_overlays was a FAMILY in the live pipeline and it is absent
 * from the 73. The references place text most of the time; until this lands the
 * agent cannot. The family's real list came from the SCHEMA'S OWN HISTORY, not the
 * pruned enum: torn_paper, sticky_note, quote_card, lower_third, caption_match.
 * Three were retired from the enum while the record kept carrying their fields,
 * which is how a family reads as two variants and is five.
 *
 * Two torn strips slam in from opposite sides. POV hooks and BEFORE/AFTER, in
 * the old spec's own examples. Both lines are short and upper-case by
 * construction; the component renders what it is given and does not shout for you.
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
  const size = props.size || "medium";
  const position = props.position || "middle";
  const accent = props.accentColor || "#C8551F";
  const textColor = props.textColor || "#FFFFFF";
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
  const topText = String(props.topText || "");
  const bottomText = String(props.bottomText || "");
  const slideTop = (1 - ease) * -120;
  const slideBottom = (1 - ease) * 120;
  const strip = { backgroundColor: "#F7F3E8", color: "#141414", fontFamily: "sans-serif",
    fontWeight: 800, fontSize: fontSize, letterSpacing: -1, lineHeight: 1.05,
    padding: Math.round(fontSize * 0.22) + "px " + Math.round(fontSize * 0.42) + "px",
    maxWidth: "94%", whiteSpace: "normal", overflowWrap: "break-word", textAlign: "center" };
  if (!topText && !bottomText) {
    return (<div style={rootStyle}><div style={{ color: accent, fontSize: 40, fontFamily: "sans-serif" }}>NO TEXT</div></div>);
  }
  return (
    <div style={rootStyle}>
      {topText ? (<div style={{ ...strip, transform: "translateX(" + slideTop + "%) rotate(-1.5deg)" }}>{topText}</div>) : null}
      {bottomText ? (<div style={{ ...strip, backgroundColor: accent, color: textColor,
        transform: "translateX(" + slideBottom + "%) rotate(1.2deg)" }}>{bottomText}</div>) : null}
    </div>
  );
};
