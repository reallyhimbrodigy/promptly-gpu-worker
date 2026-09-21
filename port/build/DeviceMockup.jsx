/* DeviceMockup — a STILL inside a device frame, on ChatCut's timeline.
 *
 * The second of the three phantoms made real (see EvidenceCard's header for what
 * a phantom was and why these three were removed from the library before they
 * were built). Its job is to say THIS IS A SCREEN: a screenshot floating bare on
 * a frame reads as a compositing mistake, and the bezel is what makes it read as
 * a thing someone is looking at.
 *
 * THE STILL ARRIVES AS A URL STRING and is used directly as a src — measured,
 * not assumed (measured/mg_runtime_capabilities_2026-09-19.md, second run).
 *
 * THE ASPECT IS THE DEVICE'S, NOT THE STILL'S, and that is the point of a mockup:
 * a phone screen is 9:19.5 whatever you put in it, so the still is covered and
 * cropped to the device rather than the device stretched to the still. A mockup
 * that changed shape per screenshot would not be a mockup.
 *
 * NO VELOCITY CAP: no video, no ramp against a source. Exempt by nature, like the
 * tight-cut overlays, and not in the peaks table.
 *
 * CONTRACT: one top-level component, no top-level constants, plain div root,
 * values through `props`, every declared property read AND used, no hardcoded
 * fallbacks — the device and size tables are lookups keyed by a property, which
 * is not a fallback and survives the strip.
 */
const Component = ({ item }) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const props = (item && item.props) || {};
  const still = props.still;
  const device = props.device;
  const size = props.size;
  const position = props.position;
  const bezelColor = props.bezelColor;
  const showNotch = props.showNotch === true || props.showNotch === "true";

  // Real device proportions, so the mockup reads as the object it is imitating.
  const devices = {
    phone:  { aspect: 9 / 19.5, radius: 0.085, bezel: 0.020, notch: true },
    tablet: { aspect: 3 / 4,    radius: 0.045, bezel: 0.030, notch: false },
    laptop: { aspect: 16 / 10,  radius: 0.022, bezel: 0.018, notch: false },
  };
  const sizes = { small: 0.38, medium: 0.52, large: 0.66, xlarge: 0.80 };
  const places = { top: "flex-start", middle: "center", bottom: "flex-end" };
  const spec = devices[device] === undefined ? devices.phone : devices[device];
  const widthFraction = sizes[size] === undefined ? sizes.medium : sizes[size];
  const justify = places[position] === undefined ? places.middle : places[position];

  const boxWidth = Math.round(width * widthFraction);
  const boxHeight = Math.round(boxWidth / spec.aspect);
  const bezel = Math.max(4, Math.round(boxWidth * spec.bezel));
  const radius = Math.round(boxWidth * spec.radius);

  // Settles from slightly small. The device arriving is the beat; it does not
  // need to travel.
  const enter = spring({ frame, fps, config: { damping: 26, mass: 0.8, stiffness: 170 },
    durationInFrames: Math.max(2, Math.round(fps * 0.55)) });
  const scale = 0.92 + 0.08 * enter;
  const fade = Math.min(Math.max(enter * 1.4, 0), 1);

  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    alignItems: justify, justifyContent: "center", overflow: "hidden",
    boxSizing: "border-box", padding: Math.round(width * 0.05),
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
      <div style={{ width: boxWidth, height: boxHeight, backgroundColor: bezelColor,
        borderRadius: radius, padding: bezel, boxSizing: "border-box",
        opacity: fade, transform: "scale(" + scale + ")", position: "relative",
        boxShadow: "0 22px 60px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.08) inset" }}>
        <div style={{ width: "100%", height: "100%", overflow: "hidden",
          borderRadius: Math.max(2, radius - bezel), backgroundColor: "#000000" }}>
          <Img src={still} style={{ width: "100%", height: "100%",
            objectFit: "cover", display: "block" }} />
        </div>
        {showNotch && spec.notch ? (
          <div style={{ position: "absolute", top: bezel, left: "50%",
            transform: "translateX(-50%)", width: Math.round(boxWidth * 0.34),
            height: Math.round(boxWidth * 0.055), backgroundColor: bezelColor,
            borderBottomLeftRadius: Math.round(boxWidth * 0.03),
            borderBottomRightRadius: Math.round(boxWidth * 0.03) }} />
        ) : null}
      </div>
    </div>
  );
};
