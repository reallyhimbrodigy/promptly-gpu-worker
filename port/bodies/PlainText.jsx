/* NO HARDCODED FALLBACK LIVES HERE (Zac, 2026-09-20). Defaults belong to the
 * property table and nowhere else. ChatCut REWRITES the code at registration, so a
 * fallback in source is dead code that looks live — and with none to strip, the
 * registered blob comes back byte-identical and port/registered_diff.mjs can assert
 * exact equality, which is the only way to know the code that runs is the code we
 * built. */
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
  const text = String(props.text);
  const size = props.size;
  const position = props.position;
  const textColor = props.textColor;
  const nominalSize = size === "xlarge" ? 168 : size === "large" ? 128 : size === "small" ? 72 : 96;
  // FIT LONGER COPY BY SHRINKING, NEVER BY GROWING (Zac 2026-09-22).
  //
  // The registered box for this component is 1080 x THE HEIGHT IT DRAWS AT
  // DEFAULT CONTENT. That makes the default string the definition of capacity:
  // anything longer must fit inside the same box, so the type gets smaller
  // rather than the box getting taller.
  //
  // WHY sqrt AND NOT A LINEAR FACTOR. At a fixed width, characters-per-line
  // scales as 1/fontSize and line count as chars*fontSize/width, so
  // height = lines * fontSize is proportional to chars * fontSize^2. Holding
  // height constant therefore needs fontSize proportional to 1/sqrt(chars).
  // A linear factor over-shrinks hard and would make a 2x string half-size
  // when it only needs 1/1.41.
  //
  // FIT_REF_CHARS IS THE REGISTERED DEFAULT'S LENGTH — 'THIS IS THE PART THAT MATTERS' — so the default
  // content renders byte-identically to today (fit clamps to 1) and only
  // longer copy moves. If the registered default changes, this constant is
  // stale and the box it was measured for is wrong; a leg asserts they agree.
  //
  // THE FLOOR IS A REAL LIMIT, STATED: below 24px the box CAN be exceeded.
  // That needs 464 characters at this nominal size, which no plausible copy
  // reaches — but it is a bound, not an impossibility, and the per-component
  // wrap leg is what would catch it.
  const FIT_REF_CHARS = 29;
  const fit = Math.min(1, Math.sqrt(FIT_REF_CHARS / Math.max(1, String(text || "").length)));
  const fontSize = Math.max(24, Math.round(nominalSize * fit));
  const justify = position === "top" ? "flex-start" : position === "bottom" ? "flex-end" : "center";
  const pad = Math.round(fontSize * 0.9);
  // THE FACE IS A font-TYPED PROPERTY, NOT A CSS STRING. Measured 2026-09-19:
  // two caption styles differing ONLY in family rendered PIXEL-IDENTICAL, because a
  // bare fontFamily names a face the renderer was never told to fetch. Only a
  // declared `font` property loads one. The default is a CANONICAL name confirmed
  // present by search_fonts — "Georgia" is NOT in the catalogue (it answers with
  // Noto Sans/Serif Georgian, which are Georgian-SCRIPT faces), so the serif here
  // is Lora, which is.
  const fontFamily = props.fontFamily;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    flexDirection: "column", alignItems: "center", justifyContent: justify,
    overflow: "hidden", boxSizing: "border-box", padding: pad };
  // Entrance eases POSITION, never opacity: FRAME-1-IS-FINAL for readable text.
  const t = Math.min(Math.max(frame / Math.max(1, Math.round(0.28 * fps)), 0), 1);
  const ease = 1 - Math.pow(1 - t, 3);
  const rise = (1 - ease) * 26;
  if (!text) {
    // RENDERS NOTHING, NOT A PLACEHOLDER (Zac 2026-09-22). This returned the
    // words "NO TEXT" — an error message drawn on the user's video, which is the
    // NO STILL family: a degraded fallback that ships the component's internal
    // state as content. Six of the twelve bodies carried one; EmojiCard was
    // only the one that got CAUGHT, because its trigger property defaults to
    // empty and so the default placement hit it.
    //
    // An empty root, not `return null`: the ChatCut contract wants a plain div
    // root, and an empty div renders nothing while still satisfying it.
    //
    // The absence is not silent — the delivery read-back flags a text component
    // placed with empty content. That is the right place for it: the editor
    // should be told, on OUR surface, rather than the viewer being shown a
    // string on THEIRS.
    return <div style={rootStyle} />;
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
