/* NO HARDCODED FALLBACK LIVES HERE (Zac, 2026-09-20). Defaults belong to the
 * property table and nowhere else. ChatCut REWRITES the code at registration, so a
 * fallback in source is dead code that looks live — and with none to strip, the
 * registered blob comes back byte-identical and port/registered_diff.mjs can assert
 * exact equality, which is the only way to know the code that runs is the code we
 * built. */
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
  const size = props.size;
  const position = props.position;
  const accent = props.accentColor;
  const textColor = props.textColor;
  // THE REFERENCE SCALE, the same ladder the component sheet already uses.
  const name = String(props.name);
  const title = String(props.title);
  // FIT LONGER COPY BY SHRINKING, NEVER BY GROWING. Measured by Builder 1
  // at 2x the baked default: this component drew past its registered height
  // with nothing stopping it, because it had no shrink at all while
  // CaptionMatch, PlainText and QuoteCard all carry one.
  //
  // COMBINED LENGTH, because both fields share one stack and either can push
  // the height. FIT_REF_CHARS is "ALEX RIVERA" + "FOUNDER, PROMPTLY" = 28.
  //
  // THE FLOOR IS 24, MATCHING THE OTHER THREE, AND THE FLOOR IS WHAT BOUNDS
  // IT — stated rather than implied. 96 * sqrt(28/N) reaches 24 at N = 448
  // characters, so below that the type shrinks and the box holds; past it the
  // floor stops the shrink and the text wraps. 448 characters across a name and
  // a role is not a case this component has; EmojiCard's floor of 14 bites at
  // 86, which is why THAT one needed a hard max and this does not.
  const FIT_REF_CHARS = 28;
  const fitLen = Math.max(1, name.length + title.length);
  const fit = Math.min(1, Math.sqrt(FIT_REF_CHARS / fitLen));
  const nominalSize = size === "xlarge" ? 168 : size === "large" ? 128 : size === "small" ? 72 : 96;
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
  const wipe = Math.round(ease * 100);
  if (!name) {
    // RENDERS NOTHING, NOT A PLACEHOLDER (Zac 2026-09-22). This returned the
    // words "NO NAME" — an error message drawn on the user's video, which is the
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
      <div style={{ alignSelf: "flex-start", clipPath: "inset(0 " + (100 - wipe) + "% 0 0)" }}>
        <div style={{ backgroundColor: "rgba(12,12,14,0.9)", padding: Math.round(fontSize * 0.34),
                      borderBottom: Math.round(fontSize * 0.07) + "px solid " + accent }}>
          {/* lineHeight 1.25, WAS 1.05. THE NAME WAS DRAWN OUTSIDE ITS OWN
              BACKGROUND. The dark box sizes to this div's LINE BOX, and at
              1.05 an 800-weight uppercase face's ink is taller than the line
              box it sits in — so the caps spilled above the painted
              background and the box's top edge ran through the middle of
              "ALEX RIVERA", half on the box and half on the video.

              Not a clipping bug: nothing was cut off. The text was outside
              the thing meant to be behind it, which looks like clipping and
              is fixed at the opposite end — make the box taller, not the
              text smaller. Same family as StatCard's lineHeight 1, where the
              line box cropped the digits instead. */}
          <div style={{ color: textColor, fontFamily: fontFamily, fontWeight: 800,
                        fontSize: fontSize, lineHeight: 1.25 }}>{name}</div>
          {title ? (<div style={{ color: accent, fontFamily: fontFamily, fontWeight: 600,
                                  fontSize: Math.round(fontSize * 0.42),
                                  marginTop: Math.round(fontSize * 0.12) }}>{title}</div>) : null}
        </div>
      </div>
    </div>
  );
};
