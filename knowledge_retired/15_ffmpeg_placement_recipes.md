=== COPY-READY FFMPEG RECIPES — CARDS & OVERLAY TEXT ===
═══════════════════════════════════════════════════════════════════════════

Rules 14 tells you WHERE families belong. This file is HOW to render them.
Every snippet below is copy-ready against a 1080x1920 frame. Change the text,
the timings and the y-position; leave the structure alone.

Font path in this image: /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
Check it once with `ls` before your first render; if it is missing, find one
with `fc-list | head` and substitute.

TIMING IS THE POINT. Every element is gated with
  enable='between(t,START,END)'
where START/END are SECONDS IN THE OUTPUT timeline (after your cuts), not in
the source. Get these from your own cut list, not from the source transcript.

──────────────────────────────────────────
RECIPE 1 — POSITIONED OVERLAY TEXT
──────────────────────────────────────────
The workhorse. Text riding the speaker at a claim. Upper third, centred,
with a shadow so it survives a bright frame.

  ffmpeg -y -i in.mp4 -vf "
  drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:
  text='THE PART THEY NEVER TELL YOU':
  fontcolor=white:fontsize=64:
  shadowcolor=black@0.8:shadowx=3:shadowy=3:
  x=(w-text_w)/2:y=h*0.18:
  enable='between(t,3.2,6.4)'
  " -c:v libx264 -crf 18 -preset medium -c:a copy out.mp4

  Notes:
  - `x=(w-text_w)/2` centres it. NEVER hardcode an x — text width varies.
  - y=h*0.18 is upper third; y=h*0.72 is lower third (above the caption band).
  - Escape apostrophes in text as '\\''  or avoid them.
  - Keep it SHORT. Two to five words. It is a caption for the idea, not a
    sentence.

──────────────────────────────────────────
RECIPE 2 — A CARD (box + hero number + label)
──────────────────────────────────────────
The close instrument. A card is a BOX plus text drawn on top of it, in one
filter chain. drawbox first, drawtext second — order is the z-order.

  ffmpeg -y -i in.mp4 -vf "
  drawbox=x=140:y=h*0.34:w=800:h=420:color=black@0.72:t=fill:
  enable='between(t,12.0,16.0)',
  drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:
  text='100K':fontcolor=white:fontsize=190:
  x=(w-text_w)/2:y=h*0.40:
  enable='between(t,12.0,16.0)',
  drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:
  text='SUBSCRIBERS':fontcolor=white@0.85:fontsize=46:
  x=(w-text_w)/2:y=h*0.60:
  enable='between(t,12.0,16.0)'
  " -c:v libx264 -crf 18 -preset medium -c:a copy out.mp4

  Notes:
  - ALL THREE share the same enable window. A box that outlives its text is
    the most common way this looks broken.
  - The number is QUOTED FROM THE DIALOGUE. If the speaker did not say a
    number, this is not a card — use overlay text.
  - Drop the drawbox for a background-free card (the number floating over
    footage). That is a legitimate style and the catalogue's default.

──────────────────────────────────────────
RECIPE 3 — SEVERAL PLACEMENTS + CAPTIONS IN ONE PASS
──────────────────────────────────────────
Chain them with commas in a single -vf. ONE encode, not one per element —
re-encoding per element compounds generation loss and costs multiples.

Captions ride an ASS file; overlays are drawtext in the SAME chain:

  ffmpeg -y -i cut.mp4 -vf "
  subtitles=/work/captions.ass,
  drawtext=fontfile=$F:text='FIRST CLAIM':fontcolor=white:fontsize=60:
    shadowcolor=black@0.8:shadowx=3:shadowy=3:
    x=(w-text_w)/2:y=h*0.18:enable='between(t,2.0,4.5)',
  drawtext=fontfile=$F:text='THE TURN':fontcolor=white:fontsize=60:
    shadowcolor=black@0.8:shadowx=3:shadowy=3:
    x=(w-text_w)/2:y=h*0.18:enable='between(t,11.0,13.2)',
  drawbox=x=140:y=h*0.34:w=800:h=420:color=black@0.72:t=fill:
    enable='between(t,24.0,27.5)',
  drawtext=fontfile=$F:text='3X':fontcolor=white:fontsize=190:
    x=(w-text_w)/2:y=h*0.42:enable='between(t,24.0,27.5)'
  " -c:v libx264 -crf 18 -preset medium -c:a copy out.mp4

  Set F once:  F=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf

──────────────────────────────────────────
WHY THIS FILE EXISTS
──────────────────────────────────────────
Three consecutive renders placed ZERO cards and ZERO overlay text while the
placement rules were loaded and read. Knowing where a card belongs is not the
same as knowing the invocation that draws one. If you now place them, the gap
was the invocation. Use these.

Captions alone are not a directed edit. An edit with cuts and captions and
nothing else is the floor, not the deliverable.


──────────────────────────────────────────
RECIPE 4 — A REMOTION COMPONENT (VERIFIED, NOT INVENTED)
──────────────────────────────────────────
MEASURED in this exact container: 30 frames in 10.3s = 343.3 ms/frame, output
1080x1920 h264. This command works as written:

  cd /promptly-remotion && npx remotion render PromptlyOverlay /work/mg.mp4 --frames=0-29

PromptlyOverlay carries WORKING defaultProps — it renders with NO --props.
Get a file out of it FIRST, then add props if you need them, via a FILE
(--props=/tmp/props.json), never inline JSON in a shell command.

`npx remotion compositions` lists what exists (verified exit 0).

RENDER ONE REAL COMPONENT — the SHORT path. MGCraftProbe mounts a REAL
component from the catalogue by name. It is NOT a fake: `type` selects the
actual StatCard/ProgressBar/etc. Do NOT try to drive PromptlyOverlay for a
single graphic — that composition wants a whole edit plan and is the wrong
entry point for one card.

A staged, valid props file is already in the image:

  cat /promptly-remotion/example-statcard-props.json
  {"type":"StatCard","motionBlur":true,
   "props":{"value":1000000,"fromValue":10000,"prefix":"$",
            "label":"IN ASSETS","durationMs":2000}}

  # 1) USE MGCraftProbe30 — MGCraftProbe is 60fps and your edit is 30.
  cp /promptly-remotion/example-statcard-props.json /work/mg-props.json
  # (edit value / fromValue / prefix / label to YOUR quoted number)
  cd /promptly-remotion && npx remotion render MGCraftProbe30 /work/mg.mov \
    --props=/work/mg-props.json --frames=0-59

  # 2) IT RENDERS ON AN OPAQUE GREY BACKDROP (0x808080) — NOT alpha. The probe
  #    is a craft harness and paints a neutral field behind the component. Key
  #    it out before compositing, or you will paste a grey rectangle over your
  #    footage:
  cd /work && ffmpeg -y -i mg.mov \
    -vf "colorkey=0x808080:0.15:0.05,format=yuva420p" -c:v qtrle mg_keyed.mov

  # 3) Composite the KEYED file:
  cd /work && ffmpeg -y -i cut.mp4 -i mg_keyed.mov -filter_complex \
    "[1:v]setpts=PTS+13.6/TB[mg];[0:v][mg]overlay=0:0:enable='between(t,13.6,15.6)'" \
    -c:a copy out.mp4

  MEASURED: a previous run spent FOURTEEN commands rediscovering the fps and
  the grey backdrop, including dumping raw pixel values to identify the colour.
  Those three commands above are that discovery, already done.

Copy that file, change `value` / `fromValue` / `prefix` / `label` to YOUR
quoted number, and render. StatCard COUNTS UP from fromValue to value — that
motion is the entire reason to use a component instead of drawtext.

COST: ~343 ms/frame means 3s of component at 30fps = ~31s of paint, on top of
your ffmpeg edit. Use a component when the graphic MOVES (count-up number,
filling bar, staged reveal). Static text stays ffmpeg — it is correct there and
far cheaper.
