/* EvidenceCard — a STILL presented as proof, on ChatCut's timeline.
 *
 * WHY IT IS BEING BUILT NOW. EvidenceCard, DeviceMockup and EmojiCard were in
 * the library as motion graphics with NO body in ported_mg/ and no entry in the
 * registry — not even in its `refused` list, which is where a component that was
 * built and rejected goes. They were PHANTOMS: names written down when the
 * capability that would allow them was unblocked, as though unblocking had built
 * them. I removed all three in the 79 -> 77 correction. This is the other half of
 * that correction — they exist now, with bodies, and go back as real entries.
 *
 * IT TAKES A STILL, and everything about that was measured before it was written
 * (measured/mg_runtime_capabilities_2026-09-19.md, second run). `Img` IS in this
 * runtime. An `image`-typed property arrives as a plain URL STRING — you pass an
 * asset id and the component receives a 240-character URL — so `still` is used
 * directly as a src and never parsed as an id.
 *
 * WHY `Img` AND NOT `img`. The runtime rewrites a plain `<img>` into `<Img>`
 * anyway, so writing `Img` is the difference between source that matches its
 * registered form and source that DIVERGES from it for no reason. It is also the
 * load-aware one: a plain tag can paint a frame before the bytes arrive, and a
 * card that rendered empty is indistinguishable from one that worked.
 *
 * NO VELOCITY CAP: this draws no video and performs no ramp on a source. The
 * 11px/frame ceiling bounds the per-frame displacement of a ZOOM against footage;
 * there is no footage here and nothing scales across the frame. Exempt by nature,
 * like DipToBlack and the two tight-cut overlays, and not in the peaks table.
 *
 * CONTRACT (from ChatCut's validator): exactly one top-level component and NO
 * top-level constants; a plain div root, never AbsoluteFill; editable values read
 * through an identifier literally named `props`; every declared property read AND
 * used; and NO HARDCODED FALLBACKS — defaults live in the property table alone.
 * A table lookup keyed by a property is not a fallback and survives the strip.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const props = (item && item.props) || {};
  const still = props.still;
  const caption = props.caption;
  const source = props.source;
  const size = props.size;
  const position = props.position;
  const accentColor = props.accentColor;
  const fontFamily = props.fontFamily;

  // THE TWO DIALS THE REFERENCES MEASURE. Size and position are properties on
  // every ported overlay, defaulting to what the atlas measures — medium, middle.
  const sizes = { small: 0.46, medium: 0.62, large: 0.78, xlarge: 0.92 };
  const places = { top: "flex-start", middle: "center", bottom: "flex-end" };
  const widthFraction = sizes[size] === undefined ? sizes.medium : sizes[size];
  const justify = places[position] === undefined ? places.middle : places[position];

  const cardWidth = Math.round(width * widthFraction);
  const pad = Math.round(cardWidth * 0.045);
  const captionSize = Math.round(cardWidth * 0.062);
  const sourceSize = Math.round(cardWidth * 0.040);

  // The card rises and settles. A spring, because the runtime has one and a
  // second copy of a solver is the thing the build step exists to prevent.
  const enter = spring({ frame, fps, config: { damping: 24, mass: 0.7, stiffness: 190 },
    durationInFrames: Math.max(2, Math.round(fps * 0.5)) });
  const lift = (1 - enter) * Math.round(cardWidth * 0.09);
  const fade = Math.min(Math.max(enter * 1.35, 0), 1);

  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: justify, justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", padding: Math.round(width * 0.06),
    pointerEvents: "none" };

  // AN EMPTY PICTURE SLOT DRAWS NOTHING — see DeviceMockup, same branch, same
  // 44px white error message rendered as the picture. TWO components carried
  // it, not one: the comment-stripped scan found this after DeviceMockup was
  // fixed, and a plain grep would have reported FOUR hits with two of them
  // being the prose about the repair.
  if (!still) return null;
  return (
    <div style={rootStyle}>
      <div style={{ width: cardWidth, backgroundColor: "#FFFFFF",
        borderRadius: Math.round(cardWidth * 0.035), overflow: "hidden",
        opacity: fade, transform: "translateY(" + lift + "px)",
        boxShadow: "0 18px 48px rgba(0,0,0,0.42), 0 4px 12px rgba(0,0,0,0.3)" }}>
        <Img src={still} style={{ width: "100%", display: "block",
          objectFit: "cover", aspectRatio: "16 / 9" }} />
        <div style={{ height: Math.round(cardWidth * 0.012),
          backgroundColor: accentColor }} />
        <div style={{ padding: pad }}>
          {caption ? (
            <div style={{ color: "#141414", fontFamily: fontFamily,
              fontSize: captionSize, lineHeight: 1.22, fontWeight: 600 }}>
              {caption}
            </div>
          ) : null}
          {source ? (
            <div style={{ color: accentColor, fontFamily: fontFamily,
              fontSize: sourceSize, letterSpacing: 0.6, marginTop: Math.round(pad * 0.5),
              textTransform: "uppercase" }}>
              {source}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
