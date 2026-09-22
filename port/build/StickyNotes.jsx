/* NO HARDCODED FALLBACK LIVES HERE (Zac, 2026-09-20). Defaults belong to the
 * property table and nowhere else. ChatCut REWRITES the code at registration, so a
 * fallback in source is dead code that looks live — and with none to strip, the
 * registered blob comes back byte-identical and port/registered_diff.mjs can assert
 * exact equality, which is the only way to know the code that runs is the code we
 * built. */
/* StickyNotes - the sticky_note text overlay, ported from the old pipeline's family.
 *
 * ONE COMPONENT, TWO HOMES (Zac, ruling 2026-09-21, and handler.py:8287 said so
 * all along). It is emitted as a TEXT OVERLAY when the three items MARK
 * STRUCTURE - the video's own three rules, three takeaways, three chapters -
 * and as a MOTION GRAPHIC when the three items ARE the referent the speaker is
 * pointing at. Structure is an overlay; evidence is a graphic. Never both for
 * one moment. It is ONE component and it is routed, never duplicated.
 *
 * THREE NOTES IS THE POINT; ONE IS THE DEGENERATE CASE. The live prompt is
 * explicit - "the three-note rhythm is the moment, the stagger, the slam, the
 * three ideas landing as one" - and the property default is three accordingly.
 *
 * THIS FLATTENED BODY *IS* THE PORT. ChatCut's property schema has no array
 * type, so the notes arrive as text|colour|rotation separated by semicolons.
 * That is a TRANSPORT difference, not a different component: the registry's old
 * `refused` row for the array-typed shape is superseded by this, not standing
 * as a refusal.
 *
 * WHAT I GOT WRONG, KEPT BECAUSE THE NEXT PERSON WILL BE TEMPTED THE SAME WAY.
 * I ported this with a ONE-note default that I chose, then read that default
 * back as evidence that the component was singular, then had it split from the
 * motion graphic and renamed HandwrittenNote on the strength of it. The
 * evidence was manufactured by the act it was meant to justify. handler.py:8287
 * had the correct description the entire time and I did not read it until the
 * rename was already landed.
 *
 * WHY IT IS BACK. text_overlays was a FAMILY in the live pipeline and it is absent
 * from the 73. The references place text most of the time; until this lands the
 * agent cannot. The family's real list came from the SCHEMA'S OWN HISTORY, not the
 * pruned enum: torn_paper, sticky_note, quote_card, lower_third, caption_match.
 * Three were retired from the enum while the record kept carrying their fields,
 * which is how a family reads as two variants and is five.
 *
 * THREE handwritten-style notes by default, one to three by range. Takeaways, tips, the educational beat.
 * ChatCut's property schema has NO ARRAY type (text, number, color, boolean,
 * select, font, image, video), so the notes arrive as text|color|rotation
 * separated by semicolons, and a malformed entry is DROPPED AND NAMED in the
 * frame rather than read as an empty note.
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
  // accentColor DROPPED, NOT REWIRED (2026-09-22). Checked before deciding:
  // across this body's whole history `accent` appeared EXACTLY TWICE — the
  // binding, and the colour of the "NO NOTES" placeholder string. It has never
  // tinted anything the viewer was meant to see. Removing the placeholder did
  // not kill a dial; it revealed that the dial was only ever wired to the
  // error message.
  //
  // So finding it a job would be inventing a decorative use to justify a
  // property, and a dial that exists because it was already declared is worse
  // than one that does not exist: it is REGISTERED and SETTABLE, so their agent
  // can spend a choice on it and change nothing, with nothing saying so. That
  // is "registered default is the value" from the other end.
  //
  // THE PROPERTY AND THE BINDING MUST GO TOGETHER. The contract refuses a read
  // that is never used AND a declared property that is never read, so Builder 1
  // removes accentColor from PORTED_PROPS in the same pass. Half of this change
  // is a different contract violation from the half it fixes.
  // NO textColor HERE. Each note carries its own paper colour and the ink is fixed
  // dark so it stays legible on any of them. ChatCut refuses a property read into a
  // binding that is never used, so declaring one this component cannot honour is not
  // a harmless extra — it is a refusal.
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
  const fontFamily = props.fontFamily;
  const rootStyle = { position: "absolute", inset: 0, display: "flex",
    flexDirection: "column", alignItems: "center", justifyContent: justify,
    overflow: "hidden", boxSizing: "border-box", padding: pad,
    gap: Math.round(fontSize * 0.3) };
  // Entrance eases POSITION, never opacity: this repo's caption law is
  // FRAME-1-IS-FINAL for readable text, so the words are legible on frame one.
  const t = Math.min(Math.max(frame / Math.max(1, Math.round(0.28 * fps)), 0), 1);
  const ease = 1 - Math.pow(1 - t, 3);
  const notesRaw = String(props.notes);
  // A MALFORMED ENTRY IS NOT DRAWN AND NOT ANNOUNCED HERE. An earlier version
  // rendered "dropped N malformed entries" into the frame; an error rendered into a
  // user's video is worse than an empty note. The harness reads the property at the
  // rewatch and the read-back and raises it as a FAULT that withholds the export, so
  // the agent sees it and the viewer never can.
  const notes = [];
  for (const part of notesRaw.split(";")) {
    if (!part.trim()) { continue; }
    const bits = part.split("|");
    if (!bits[0] || !bits[0].trim()) { continue; }
    const rot = Number(bits[2]);
    notes.push({ text: bits[0].trim(),
                 color: (bits[1] || "#FFE066").trim(),
                 rotation: isFinite(rot) ? rot : 0 });
  }
  if (!notes.length) {
    // RENDERS NOTHING, NOT A PLACEHOLDER (Zac 2026-09-22). This returned the
    // words "NO NOTES" — an error message drawn on the user's video, which is the
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
      {notes.slice(0, 3).map((n, i) => (
        <div key={i} style={{
          backgroundColor: n.color, color: "#141414", fontFamily: fontFamily,
          fontSize: Math.round(fontSize * 0.72), lineHeight: 1.16,
          padding: Math.round(fontSize * 0.36), maxWidth: "76%",
          whiteSpace: "normal", overflowWrap: "break-word",
          boxShadow: "0 10px 26px rgba(0,0,0,0.4)",
          transform: "rotate(" + n.rotation + "deg) translateY(" + ((1 - ease) * (26 + i * 10)) + "px)" }}>
          {n.text}
        </div>))}
    </div>
  );
};
