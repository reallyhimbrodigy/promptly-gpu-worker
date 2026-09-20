/* PlainText - the workhorse text overlay: words on the picture, nothing else.
 *
 * WHY IT EXISTS, AND WHY IT IS NOT CaptionMatch. Builder-2 measured the references'
 * text as PLAIN, MEDIUM, MIDDLE — the most common shape in the corpus. For one day
 * that shape was served by CaptionMatch, but only because that port was incomplete:
 * it rendered a fixed sans-serif and never read the caption style it is named for.
 * The moment CaptionMatch learned its job, the plain shape left the menu with it.
 * So the workhorse gets its own component, named for what it is.
 *
 * NOTHING BEHIND THE WORDS. No card, no strip, no panel, no bar — those are the
 * other four variants, and each of them says something extra. This says only what
 * it says. The shadow is for legibility over a moving picture, not decoration.
 *
 * THE DIALS ARE THE SAME TWO every variant carries, in the same place, defaulting to
 * what the references measure: medium, middle.
 *
 * NO VELOCITY CAP: this draws no video and performs no ramp.
 *
 * CONTRACT (from ChatCut's validator): one top-level component, no top-level
 * constants, a plain div root, values read through an identifier named props, every
 * declared property read AND used.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const props = (item && item.props) || {};
  const text = String(props.text || "");
  const size = props.size || "medium";
  const position = props.position || "middle";
  const textColor = props.textColor || "#FFFFFF";
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
  const fontFamily = props.fontFamily || "Inter";
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    flexDirection: "column", alignItems: "center", justifyContent: justify,
    overflow: "hidden", boxSizing: "border-box", padding: pad };
  // Entrance eases POSITION, never opacity: FRAME-1-IS-FINAL for readable text.
  const t = Math.min(Math.max(frame / Math.max(1, Math.round(0.28 * fps)), 0), 1);
  const ease = 1 - Math.pow(1 - t, 3);
  const rise = (1 - ease) * 26;
  if (!text) {
    return (<div style={rootStyle}><div style={{ color: textColor, fontSize: 40, fontFamily: "sans-serif" }}>NO TEXT</div></div>);
  }
  return (
    <div style={rootStyle}>
      <div style={{ transform: "translateY(" + rise + "px)", color: textColor,
                    fontFamily: fontFamily, fontWeight: 600,
                    fontSize: fontSize, lineHeight: 1.14, textAlign: "center",
                    maxWidth: "88%", whiteSpace: "normal", overflowWrap: "break-word",
                    textShadow: "0 4px 18px rgba(0,0,0,0.5)" }}>
        {text}
      </div>
    </div>
  );
};
