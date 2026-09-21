/* EmojiCard — a STILL with a reaction pinned to it, on ChatCut's timeline.
 *
 * The third phantom made real (see EvidenceCard's header). Where EvidenceCard
 * says THIS IS PROOF and DeviceMockup says THIS IS A SCREEN, this one says HOW TO
 * FEEL ABOUT IT — the reaction is the editorial, and the still is what it is
 * reacting to.
 *
 * THE EMOJI IS TEXT, NOT AN IMAGE, deliberately. An emoji shipped as an asset is
 * a second upload, a second thing to go missing, and a fixed rendering; as text
 * it is one property the editor can type into. The badge lands on a spring AFTER
 * the card, because a reaction that arrives at the same instant as the thing it
 * reacts to reads as decoration rather than as a response.
 *
 * THE STILL ARRIVES AS A URL STRING (measured, second run of the runtime probe).
 *
 * NO VELOCITY CAP: no video, no ramp against a source. The badge's pop is a
 * scale on a small element over ~0.4s, not a zoom across the frame — the ceiling
 * exists to bound judder on footage and there is no footage here.
 *
 * CONTRACT: one top-level component, no top-level constants, plain div root,
 * values through `props`, every declared property read AND used, no hardcoded
 * fallbacks.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const props = (item && item.props) || {};
  const still = props.still;
  const emoji = props.emoji;
  const caption = props.caption;
  const size = props.size;
  const position = props.position;
  const accentColor = props.accentColor;
  const fontFamily = props.fontFamily;

  const sizes = { small: 0.44, medium: 0.58, large: 0.72, xlarge: 0.86 };
  const places = { top: "flex-start", middle: "center", bottom: "flex-end" };
  const widthFraction = sizes[size] === undefined ? sizes.medium : sizes[size];
  const justify = places[position] === undefined ? places.middle : places[position];

  const cardWidth = Math.round(width * widthFraction);
  const badge = Math.round(cardWidth * 0.26);
  const captionSize = Math.round(cardWidth * 0.058);

  const enter = spring({ frame, fps, config: { damping: 24, mass: 0.7, stiffness: 190 },
    durationInFrames: Math.max(2, Math.round(fps * 0.5)) });
  const lift = (1 - enter) * Math.round(cardWidth * 0.08);
  const fade = Math.min(Math.max(enter * 1.35, 0), 1);
  // THE REACTION LANDS SECOND. Delayed by ~0.22s so it reads as a response.
  const pop = spring({ frame: frame - Math.round(fps * 0.22), fps,
    config: { damping: 12, mass: 0.6, stiffness: 240 },
    durationInFrames: Math.max(2, Math.round(fps * 0.4)) });
  const badgeScale = Math.min(Math.max(pop, 0), 1.08);

  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: justify, justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", padding: Math.round(width * 0.07),
    pointerEvents: "none" };

  if (!still) {
    return (
      <div style={rootStyle}>
        <div style={{ color: "#FFFFFF", fontSize: 44, fontFamily: "sans-serif" }}>
          NO STILL
        </div>
      </div>
    );
  }
  return (
    <div style={rootStyle}>
      <div style={{ width: cardWidth, position: "relative", opacity: fade,
        transform: "translateY(" + lift + "px)" }}>
        <div style={{ width: "100%", borderRadius: Math.round(cardWidth * 0.05),
          overflow: "hidden", border: Math.round(cardWidth * 0.012) + "px solid " + accentColor,
          boxSizing: "border-box", backgroundColor: "#000000",
          boxShadow: "0 18px 46px rgba(0,0,0,0.45)" }}>
          <Img src={still} style={{ width: "100%", display: "block",
            objectFit: "cover", aspectRatio: "4 / 5" }} />
        </div>
        {emoji ? (
          <div style={{ position: "absolute", right: -Math.round(badge * 0.22),
            top: -Math.round(badge * 0.22), width: badge, height: badge,
            borderRadius: "50%", backgroundColor: "#FFFFFF",
            display: "flex", alignItems: "center", justifyContent: "center",
            transform: "scale(" + badgeScale + ")",
            boxShadow: "0 10px 26px rgba(0,0,0,0.45)" }}>
            <span style={{ fontSize: Math.round(badge * 0.58), lineHeight: 1 }}>
              {emoji}
            </span>
          </div>
        ) : null}
        {caption ? (
          <div style={{ marginTop: Math.round(cardWidth * 0.045), textAlign: "center",
            color: "#FFFFFF", fontFamily: fontFamily, fontSize: captionSize,
            fontWeight: 600, textShadow: "0 2px 10px rgba(0,0,0,0.65)" }}>
            {caption}
          </div>
        ) : null}
      </div>
    </div>
  );
};
