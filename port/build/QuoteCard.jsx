/* NO HARDCODED FALLBACK LIVES HERE (Zac, 2026-09-20). Defaults belong to the
 * property table and nowhere else. ChatCut REWRITES the code at registration, so a
 * fallback in source is dead code that looks live — and with none to strip, the
 * registered blob comes back byte-identical and port/registered_diff.mjs can assert
 * exact equality, which is the only way to know the code that runs is the code we
 * built. */
/* QuoteCard - the quote_card text overlay, ported from the old pipeline's family.
 *
 * WHY IT IS BACK. text_overlays was a FAMILY in the live pipeline and it is absent
 * from the 73. The references place text most of the time; until this lands the
 * agent cannot. The family's real list came from the SCHEMA'S OWN HISTORY, not the
 * pruned enum: torn_paper, sticky_note, quote_card, lower_third, caption_match.
 * Three were retired from the enum while the record kept carrying their fields,
 * which is how a family reads as two variants and is five.
 *
 * A floating card carrying a quote and an em-dash attribution, serif and
 * premium. Testimonials, pull-quotes, a line from a book. The em dash belongs to
 * the component, not the author - passing one in the attribution double-prints it.
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
  // HOISTED ABOVE `nominalSize` BECAUSE THE FIT LINE BELOW READS IT.
  // `const` has a temporal dead zone, so a reference above the
  // declaration is a ReferenceError — ChatCut's validator catches it
  // statically and REFUSES the whole component: 'Undefined identifier
  // "quote". Declare it locally, read it from props, ...'
  //
  // It got that way because removing the placeholder branch deleted the
  // only thing standing between the use and the declaration. And the
  // declaration moves UP rather than the fit block moving DOWN: `pad`
  // and the flex `gap` both read fontSize above here, so lowering it
  // trades one dead-zone error for two. I made exactly that trade on
  // the first attempt and the head-runner caught it.
  const quote = String(props.quote);

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
  // FIT_REF_CHARS IS THE REGISTERED DEFAULT'S LENGTH — "You don't need more time. You need fewer excuses." — so the default
  // content renders byte-identically to today (fit clamps to 1) and only
  // longer copy moves. If the registered default changes, this constant is
  // stale and the box it was measured for is wrong; a leg asserts they agree.
  //
  // THE FLOOR IS A REAL LIMIT, STATED: below 24px the box CAN be exceeded.
  // That needs 784 characters at this nominal size, which no plausible copy
  // reaches — but it is a bound, not an impossibility, and the per-component
  // wrap leg is what would catch it.
  const FIT_REF_CHARS = 49;
  const fit = Math.min(1, Math.sqrt(FIT_REF_CHARS / Math.max(1, String(quote || "").length)));
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
    overflow: "hidden", boxSizing: "border-box", padding: pad,
    gap: Math.round(fontSize * 0.3) };
  // Entrance eases POSITION, never opacity: this repo's caption law is
  // FRAME-1-IS-FINAL for readable text, so the words are legible on frame one.
  const t = Math.min(Math.max(frame / Math.max(1, Math.round(0.28 * fps)), 0), 1);
  const ease = 1 - Math.pow(1 - t, 3);
  const attribution = String(props.attribution);
  const rise = (1 - ease) * 40;
  if (!quote) {
    // RENDERS NOTHING, NOT A PLACEHOLDER (Zac 2026-09-22). This returned the
    // words "NO QUOTE" — an error message drawn on the user's video, which is the
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
      <div style={{ transform: "translateY(" + rise + "px)", maxWidth: "92%",
                    backgroundColor: "rgba(12,12,14,0.86)", padding: Math.round(fontSize * 0.55),
                    borderLeft: Math.round(fontSize * 0.09) + "px solid " + accent }}>
        <div style={{ color: textColor, fontFamily: fontFamily, fontSize: fontSize,
                      lineHeight: 1.22, whiteSpace: "normal", overflowWrap: "break-word" }}>
          {quote}
        </div>
        {attribution ? (
          <div style={{ color: accent, fontFamily: fontFamily,
                        fontSize: Math.round(fontSize * 0.46),
                        marginTop: Math.round(fontSize * 0.3) }}>
            {"\u2014 " + attribution}
          </div>) : null}
      </div>
    </div>
  );
};
