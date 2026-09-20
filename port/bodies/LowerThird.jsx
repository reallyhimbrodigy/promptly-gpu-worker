/* LowerThird - the lower_third text overlay, ported from the old pipeline's family.
 *
 * WHY IT IS BACK. text_overlays was a FAMILY in the live pipeline and it is absent
 * from the 73. The references place text most of the time; until this lands the
 * agent cannot. The family's real list came from the SCHEMA'S OWN HISTORY, not the
 * pruned enum: torn_paper, sticky_note, quote_card, lower_third, caption_match.
 * Three were retired from the enum while the record kept carrying their fields,
 * which is how a family reads as two variants and is five.
 *
 * A broadcast name-and-title card. Speaker attribution, podcast guests, location
 * tags - the old spec emitted ONE per distinct speaker. Its natural home is the
 * lower third, so position defaults there for this one variant and the dial still moves it.
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
  const position = props.position || "bottom";
  const accent = props.accentColor || "#C8551F";
  const textColor = props.textColor || "#FFFFFF";
  // THE REFERENCE SCALE, the same ladder the component sheet already uses.
  const fontSize = size === "xlarge" ? 168 : size === "large" ? 128 : size === "small" ? 72 : 96;
  const justify = position === "top" ? "flex-start" : position === "bottom" ? "flex-end" : "center";
  const pad = Math.round(fontSize * 0.9);
  // THE FACE IS A font-TYPED PROPERTY, NOT A CSS STRING. Measured 2026-09-19:
  // two caption styles differing ONLY in family rendered PIXEL-IDENTICAL, because a
  // bare fontFamily names a face the renderer was never told to fetch. Only a
  // declared `font` property loads one. The default is a CANONICAL name confirmed
  // present by search_fonts — "Georgia" is NOT in the catalogue (it answers with
  // Noto Sans/Serif Georgian, which are Georgian-SCRIPT faces), so the serif here
  // is Lora, which is.
  const fontFamily = props.fontFamily || "Montserrat";
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    flexDirection: "column", alignItems: "center", justifyContent: justify,
    overflow: "hidden", boxSizing: "border-box", padding: pad,
    gap: Math.round(fontSize * 0.3) };
  // Entrance eases POSITION, never opacity: this repo's caption law is
  // FRAME-1-IS-FINAL for readable text, so the words are legible on frame one.
  const t = Math.min(Math.max(frame / Math.max(1, Math.round(0.28 * fps)), 0), 1);
  const ease = 1 - Math.pow(1 - t, 3);
  const name = String(props.name || "");
  const title = String(props.title || "");
  const wipe = Math.round(ease * 100);
  if (!name) {
    return (<div style={rootStyle}><div style={{ color: accent, fontSize: 40, fontFamily: "sans-serif" }}>NO NAME</div></div>);
  }
  return (
    <div style={rootStyle}>
      <div style={{ alignSelf: "flex-start", clipPath: "inset(0 " + (100 - wipe) + "% 0 0)" }}>
        <div style={{ backgroundColor: "rgba(12,12,14,0.9)", padding: Math.round(fontSize * 0.34),
                      borderBottom: Math.round(fontSize * 0.07) + "px solid " + accent }}>
          <div style={{ color: textColor, fontFamily: fontFamily, fontWeight: 800,
                        fontSize: fontSize, lineHeight: 1.05 }}>{name}</div>
          {title ? (<div style={{ color: accent, fontFamily: fontFamily, fontWeight: 600,
                                  fontSize: Math.round(fontSize * 0.42),
                                  marginTop: Math.round(fontSize * 0.12) }}>{title}</div>) : null}
        </div>
      </div>
    </div>
  );
};
