"""W3 PROGRESSIVE DELIVERY (DARK behind PROMPTLY_PROGRESSIVE) — publish HLS
preview media WHILE the composite renders, so the user sees their video BEGIN
before the render finishes.

DESIGN CONTRACT (the four laws this module is built to):

  1. FINAL ARTIFACT UNTOUCHED — this module only READS the lossless
     composite_chunk_K.mov intermediates and final_audio.wav; it never writes
     into the render's own file set and never sits on the render's critical
     path. The final stitched MP4 (and its final HLS ladder) must remain
     byte/SSIM-identical to a flag-OFF render.
  2. PARTIAL IS NEVER FINAL — previews upload to a DIFFERENT S3 prefix
     ({base_key}-preview-hls/) than the final ladder's own prefix, so a
     partial manifest can never collide with the final URL; and the preview
     media playlist is a LIVE (EVENT-type) playlist WITHOUT #EXT-X-ENDLIST
     until finalize() has drained every chunk. Partial != final by
     construction, twice over.
  3. A/V LAW AT EVERY BOUNDARY — each chunk's preview segment set carries the
     exact matching audio slice (frame_start/fps .. frame_end/fps out of the
     sample-exact PCM final_audio.wav), muxed with -output_ts_offset so the
     preview timeline is continuous. Published boundaries must probe <=56ms.
  4. LOUD FALLBACK, JOB UNAFFECTED — ANY publishing error prints loudly,
     records a divergence (component="render",
     action="progressive_publish_fallback") and disables further publishing
     for the job. Event methods (begin_attempt / chunk_ready / audio_ready /
     finalize) NEVER raise into the render.

WHAT THE PREVIEW IS (and is not): a SINGLE-variant native-resolution
(1080x1920 portrait) H.264/AAC MPEG-TS rendition, encoded veryfast — good
enough to watch the edit take shape. The final 4-variant fMP4 ladder stays
the existing post-render `_encode_and_upload_hls` path, untouched. The app
swaps from the preview URL to the real final URLs when the job completes.

URL CONTRACT:
  {base_key}-preview-hls/master.m3u8    master (written once, no-cache)
  {base_key}-preview-hls/media.m3u8     LIVE media playlist (rewritten per
                                        chunk, no-cache; EVENT type; ENDLIST
                                        appears ONLY after the last chunk)
  {base_key}-preview-hls/seg_KK_NNN.ts  media segments (immutable, long cache)
  {base_key}-preview-hls/first_frame.jpg frame 1 of chunk 0 (Phase B payload)

ORDERING: chunk_ready(k, ...) events arrive IN ANY ORDER (the pipelined
composite chains run in parallel); a single daemon worker publishes strictly
IN ORDER (chunk 0, 1, 2, ...) so playback is startable at segment 1 the
moment it exists. The publisher WAITS for audio_ready() before slicing audio
— in production the composite chains are dispatched BEFORE final_audio.wav is
built, so early chunks can land before the audio exists.

RE-RENDER SAFETY: a second begin_attempt() after ANY chunk was published
(degrade-ladder retry, QA re-render) abandons the preview — mixing chunks
from two different render attempts into one manifest is never allowed. A
second attempt when NOTHING was published simply adopts the new attempt.

This module is deliberately handler-independent: S3 client, URL parser,
divergence recorder, and DB persist are injected by the caller.
"""

import math
import os
import re
import subprocess
import threading
import time

# ── Tunables (env-overridable; defaults sized for the production render) ────
class _PublishCancelled(Exception):
    """Deliberate terminal-seam cancel — worker exits quietly, never _fail."""


_AUDIO_WAIT_S = float(os.environ.get("PROMPTLY_PROGRESSIVE_AUDIO_WAIT_S", "") or 900.0)
_IDLE_ABANDON_S = float(os.environ.get("PROMPTLY_PROGRESSIVE_IDLE_S", "") or 1200.0)
_TOTAL_DEADLINE_S = float(os.environ.get("PROMPTLY_PROGRESSIVE_DEADLINE_S", "") or 7200.0)
_TRANSCODE_TIMEOUT_S = float(os.environ.get("PROMPTLY_PROGRESSIVE_ENCODE_TIMEOUT_S", "") or 600.0)
# Preview encode gets a bounded thread count so it can NEVER starve the real
# render's ffmpeg/Remotion processes (the container is cpu=128; 4 is noise).
_ENCODE_THREADS = int(os.environ.get("PROMPTLY_PROGRESSIVE_ENCODE_THREADS", "") or 4)

_PLAYLIST_CT = "application/vnd.apple.mpegurl"
_SEGMENT_CT = "video/MP2T"
# Playlists MUTATE while the render runs — they must never be edge-cached.
_PLAYLIST_CACHE = "no-cache, no-store, must-revalidate"
# Segments are immutable once written.
_SEGMENT_CACHE = "public, max-age=31536000, immutable"


def _render_master_playlist(bandwidth=6500000, resolution="1080x1920",
                            codecs="avc1.640029,mp4a.40.2"):
    """The single-variant preview master. Pure function (gate-testable)."""
    return (
        "#EXTM3U\n"
        "#EXT-X-VERSION:3\n"
        f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={resolution},"
        f'CODECS="{codecs}"\n'
        "media.m3u8\n"
    )


def _render_media_playlist(chunk_groups, final):
    """Render the preview media playlist from published chunk groups.

    chunk_groups — list (one entry per published CHUNK, in order) of lists of
                   (segment_filename, duration_seconds) tuples.
    final        — True ONLY when every chunk has been published and the real
                   final mux completed. #EXT-X-ENDLIST is written HERE AND
                   NOWHERE ELSE; a partial playlist is a LIVE playlist by
                   construction (EVENT type, no ENDLIST) so no player and no
                   cache can ever mistake it for the finished video.

    Pure function (gate-testable). Chunks are independently encoded, so each
    boundary is marked EXT-X-DISCONTINUITY; -output_ts_offset keeps the
    timeline continuous across them regardless.
    """
    durs = [d for g in chunk_groups for (_n, d) in g]
    target = max(1, int(math.ceil(max(durs)))) if durs else 1
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-TARGETDURATION:{target}",
        "#EXT-X-MEDIA-SEQUENCE:0",
        "#EXT-X-PLAYLIST-TYPE:EVENT",
        "#EXT-X-INDEPENDENT-SEGMENTS",
    ]
    for gi, group in enumerate(chunk_groups):
        if gi > 0:
            lines.append("#EXT-X-DISCONTINUITY")
        for (name, dur) in group:
            lines.append(f"#EXTINF:{dur:.5f},")
            lines.append(name)
    if final:
        lines.append("#EXT-X-ENDLIST")
    return "\n".join(lines) + "\n"


class ProgressivePublisher:
    """Accepts out-of-order chunk_ready events, publishes in order.

    Constructor RAISES on structurally unusable inputs (no S3 client,
    unparseable upload_url, missing public_url) — the caller catches, logs,
    records the divergence, and runs without previews. After construction,
    no public method ever raises.
    """

    def __init__(self, work_dir, upload_url, public_url, fps, audio_path, *,
                 s3_client, parse_s3_url, job_id="", plan_summary=None,
                 persist_cb=None, divergence_cb=None, transfer_config=None):
        if s3_client is None:
            raise RuntimeError("progressive preview requires an S3 client")
        bucket, key = parse_s3_url(upload_url)
        if not (bucket and key):
            raise RuntimeError(
                f"progressive preview could not parse S3 bucket/key from "
                f"upload_url: {str(upload_url)[:120]}")
        if not public_url:
            raise RuntimeError(
                "progressive preview requires public_url to derive the "
                "preview manifest URL")
        base_key, _ = os.path.splitext(key)
        # DISTINCT prefix from the final ladder's own — a partial preview
        # can never be served at (or collide with) the final URL.
        self._preview_prefix = f"{base_key}-preview-hls"
        _pub_no_ext, _ = os.path.splitext(str(public_url))
        self._preview_url_base = f"{_pub_no_ext}-preview-hls"
        self.preview_hls_url = f"{self._preview_url_base}/master.m3u8"

        self._work_dir = work_dir
        self._out_dir = os.path.join(work_dir, "preview_hls")
        self._bucket = bucket
        self._s3 = s3_client
        self._transfer_config = transfer_config
        self._fps = float(fps or 60.0)
        self._audio_path = audio_path
        self._job_id = job_id
        self._plan_summary = dict(plan_summary or {})
        self._persist_cb = persist_cb
        self._divergence_cb = divergence_cb

        self._cond = threading.Condition()
        self._pending = {}            # k -> (chunk_path, frame_start, frame_end)
        self._seen_k = set()
        self._groups = []             # per published chunk: [(seg_name, dur), ...]
        self._next_k = 0
        self._n_chunks = None
        self._attempts = 0
        self._audio_evt = threading.Event()
        self._finalize_requested = False
        self._cancelled = False       # deliberate terminal-seam cancel (not a defect)
        self._master_uploaded = False
        self._first_frame_url = None
        self._last_progress = time.time()
        self._started_at = None
        self._thread = None

        # Public state (read by the cert + the handler's logs).
        self.segments_published = 0   # published CHUNK count (the publish unit)
        self.disabled = False         # loud-fallback tripped: no more publishing
        self.inert = False            # single-pass render: nothing to preview
        self.finalized = False        # ENDLIST written after the LAST chunk
        self.last_payload = None      # last Phase-B payload handed to persist_cb

    # ── Event API (called from render threads; NEVER raises) ───────────────

    def begin_attempt(self, n_chunks, fps, frame_ranges=None):
        """Called at composite-chunk planning time, once per render attempt."""
        try:
            with self._cond:
                self._attempts += 1
                if self._attempts > 1:
                    if self.finalized:
                        print("[progressive] NOTE: a second render attempt "
                              "started after the preview was finalized (QA "
                              "re-render?) — the preview reflects attempt 1; "
                              "the app swaps to the final URLs on completion",
                              flush=True)
                    elif self._seen_k:
                        self._fail_locked(
                            "second_render_attempt",
                            "a re-render began after preview segments were "
                            "published — a mixed-attempt preview is never "
                            "allowed")
                    else:
                        # Nothing published yet — adopt the fresh attempt.
                        self._n_chunks = int(n_chunks or 0)
                        self._fps = float(fps or self._fps)
                    return
                if not n_chunks or int(n_chunks) <= 1:
                    # Single-pass composite (<400 frames): no chunk events
                    # will ever arrive. Not a failure — just nothing to
                    # progressively publish for so short an output.
                    self.inert = True
                    print("[progressive] single-pass composite (no chunks) — "
                          "preview publishing inert for this job", flush=True)
                    return
                self._n_chunks = int(n_chunks)
                self._fps = float(fps or self._fps)
                self._started_at = time.time()
                self._last_progress = self._started_at
                self._thread = threading.Thread(
                    target=self._run, name="progressive-publish", daemon=True)
                self._thread.start()
                print(f"[progressive] ACTIVE — {self._n_chunks} chunks will "
                      f"publish in order to s3://{self._bucket}/"
                      f"{self._preview_prefix}/ ({self.preview_hls_url})",
                      flush=True)
        except Exception as e:  # pragma: no cover — event API never raises
            self._fail("begin_attempt", e)

    def chunk_ready(self, k, chunk_path, frame_start, frame_end):
        """A composite chunk finished rendering (any order)."""
        try:
            with self._cond:
                if self.disabled or self.inert or self.finalized:
                    return
                if k in self._seen_k:
                    self._fail_locked(
                        "duplicate_chunk",
                        f"chunk {k} reported ready twice — overlapping render "
                        f"attempts; abandoning the preview")
                    return
                self._seen_k.add(k)
                self._pending[k] = (chunk_path, int(frame_start), int(frame_end))
                self._last_progress = time.time()
                self._cond.notify_all()
        except Exception as e:  # pragma: no cover — event API never raises
            self._fail("chunk_ready", e)

    def audio_ready(self):
        """final_audio.wav is complete on disk — audio slicing may begin.
        The composite chains are dispatched BEFORE the audio build in
        production, so the worker holds every publish until this fires."""
        try:
            self._audio_evt.set()
            with self._cond:
                self._cond.notify_all()
        except Exception as e:  # pragma: no cover — event API never raises
            self._fail("audio_ready", e)

    def finalize(self):
        """The REAL final concat+mux completed. Non-blocking: the worker
        writes #EXT-X-ENDLIST only after it has drained ALL chunks. Called
        best-effort from the render; a no-op when inert/disabled."""
        try:
            with self._cond:
                if self.disabled or self.inert or self.finalized:
                    return
                self._finalize_requested = True
                self._cond.notify_all()
        except Exception as e:  # pragma: no cover — event API never raises
            self._fail("finalize", e)

    @property
    def finalize_requested(self):
        return bool(self._finalize_requested)

    def drain(self, timeout_s=120.0):
        """Bounded wait for the worker to reach a terminal state (finalized /
        disabled / inert / never started). Returns True when the worker is done.
        Called at the handler's terminal seam BEFORE work_dir teardown — the
        publisher's every input and output lives inside work_dir, so teardown
        under an in-flight publish is the long-clip race (cert 2026-07-25)."""
        t = self._thread
        if t is None or not t.is_alive():
            return True
        t.join(timeout=max(0.0, float(timeout_s)))
        return not t.is_alive()

    def cancel(self, reason="terminal_teardown"):
        """Deliberate stop at the terminal seam: the FINAL artifact is already
        delivered, so the preview is moot — this is a designed path, NOT the
        loud _fail fallback (no PUBLISH FALLBACK, no defect ledger). It is
        still ledgered (progressive_cancelled) and the persisted payload is
        stamped superseded so a preview is never servable as a terminal state
        (Zac ruling 1a, 2026-07-25)."""
        try:
            with self._cond:
                if self.finalized or self.disabled or self.inert:
                    return
                self._cancelled = True
                self.disabled = True
                self._cond.notify_all()
            self._audio_evt.set()   # wake any audio-law wait immediately
            print(f"[progressive] CANCELLED ({reason}) — final delivered, "
                  f"preview publishing stopped after "
                  f"{self.segments_published} chunk group(s)", flush=True)
            try:
                if self._divergence_cb is not None:
                    self._divergence_cb(
                        "render",
                        {"stage": "cancel", "reason": reason,
                         "job_id": self._job_id,
                         "published": int(self.segments_published)},
                        "progressive_cancelled",
                        reason=f"deliberate terminal-seam cancel ({reason})")
            except Exception as de:
                print(f"[progressive] cancel divergence record failed: {de}",
                      flush=True)
            self._persist_payload(superseded=True)
        except Exception:   # never raise into the terminal seam
            pass

    # ── Worker ──────────────────────────────────────────────────────────────

    def _run(self):
        try:
            while True:
                with self._cond:
                    while True:
                        if self.disabled:
                            return
                        if self._next_k in self._pending:
                            break
                        if (self._finalize_requested
                                and self._n_chunks is not None
                                and self._next_k >= self._n_chunks):
                            break
                        now = time.time()
                        if (self._started_at is not None
                                and now - self._started_at > _TOTAL_DEADLINE_S):
                            self._fail_locked(
                                "deadline",
                                f"publisher exceeded {_TOTAL_DEADLINE_S:.0f}s "
                                f"total deadline")
                            return
                        if now - self._last_progress > _IDLE_ABANDON_S:
                            self._fail_locked(
                                "stalled",
                                f"no chunk progress for {_IDLE_ABANDON_S:.0f}s "
                                f"(render died or was torn down?)")
                            return
                        self._cond.wait(timeout=10.0)
                    if (self._finalize_requested
                            and self._n_chunks is not None
                            and self._next_k >= self._n_chunks
                            and self._next_k not in self._pending):
                        break  # every chunk published + real mux done → final
                    k = self._next_k
                    chunk_path, fs, fe = self._pending.pop(k)
                self._publish_chunk(k, chunk_path, fs, fe)
                with self._cond:
                    self._next_k += 1
                    self._last_progress = time.time()

            # ── Finalization: ENDLIST strictly AFTER the last segment ──────
            self._upload_playlists(final=True)
            with self._cond:
                self.finalized = True
            self._persist_payload()
            print(f"[progressive] FINALIZED — {self.segments_published} chunk "
                  f"group(s) published, ENDLIST written → "
                  f"{self.preview_hls_url}", flush=True)
        except _PublishCancelled as ce:
            print(f"[progressive] worker exit on cancel: {ce}", flush=True)
        except Exception as e:
            if self._cancelled:
                # teardown-adjacent noise after a deliberate cancel is not a
                # defect — the loud fallback is reserved for real publish bugs
                print(f"[progressive] post-cancel worker noise suppressed: "
                      f"{type(e).__name__}: {e}", flush=True)
            else:
                self._fail("worker", e)

    def _publish_chunk(self, k, chunk_path, frame_start, frame_end):
        t0 = time.time()
        if self._cancelled:
            raise _PublishCancelled(f"chunk {k} skipped: cancelled")
        if not os.path.exists(chunk_path) or os.path.getsize(chunk_path) < 1000:
            raise RuntimeError(
                f"chunk {k} file missing/invalid at publish time: {chunk_path}")

        # Audio law: never publish a boundary without its exact audio slice.
        # The full final_audio.wav is built in parallel with the chunks and
        # may not exist yet — wait for the render's explicit audio_ready().
        if not self._audio_evt.wait(timeout=_AUDIO_WAIT_S):
            raise RuntimeError(
                f"final audio not ready within {_AUDIO_WAIT_S:.0f}s — cannot "
                f"publish chunk {k} without its audio slice")
        if self._cancelled:   # cancel() sets the event to break the wait
            raise _PublishCancelled(f"chunk {k} skipped: cancelled during audio wait")
        if (not self._audio_path or not os.path.exists(self._audio_path)
                or os.path.getsize(self._audio_path) < 44):
            raise RuntimeError(
                f"final audio missing/invalid at {self._audio_path}")

        # First-frame still (Phase B) — best-effort, never fails the preview.
        if k == 0:
            self._extract_first_frame(chunk_path)

        os.makedirs(self._out_dir, exist_ok=True)
        fps = self._fps
        a_start = frame_start / fps
        a_end = frame_end / fps
        gop = max(1, int(round(fps * 2)))
        chunk_pl = os.path.join(self._out_dir, f"chunk_{k:02d}.m3u8")
        seg_pattern = os.path.join(self._out_dir, f"seg_{k:02d}_%03d.ts")
        cmd = [
            "ffmpeg", "-y", "-v", "error", "-threads", str(_ENCODE_THREADS),
            "-i", chunk_path,
            "-i", self._audio_path,
            "-filter_complex",
            # ProRes 4444 (yuv444p10le) → 8-bit 4:2:0 for the H.264 preview;
            # native 1080x1920 resolution (the "single 1080p variant").
            (f"[0:v]format=yuv420p[pv];"
             f"[1:a]atrim=start={a_start:.6f}:end={a_end:.6f},"
             f"asetpts=PTS-STARTPTS[pa]"),
            "-map", "[pv]", "-map", "[pa]",
            # Preset/CRF (Zac ruling 2026-07-26: minimize the visible quality
            # POP at the preview→final swap, without erasing the latency win).
            # fast/crf18 is closer to the final's look than veryfast/crf20 at a
            # small encode-time cost that stays well inside the chunk cadence;
            # -bf 0 (below) keeps the boundary-latency guarantee. The bar is
            # Zac's eye on a recorded phone swap, not an SSIM number.
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-profile:v", "high", "-level:v", "4.1",
            # -bf 0: no B-frame reordering delay. With B-frames the first TS
            # packet lands ~2 frames late (measured +67ms video start), which
            # both eats the 56ms A/V-law margin and overlaps the previous
            # chunk's tail across the discontinuity. Zero B-frames → chunks
            # start exactly on their global offset and boundaries butt
            # cleanly. Preview-only tradeoff (slightly larger segments); the
            # final artifact's encode is untouched.
            "-bf", "0",
            "-fps_mode", "cfr", "-r", str(int(round(fps))),
            "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
            "-color_primaries", "bt709", "-color_trc", "bt709",
            "-colorspace", "bt709", "-color_range", "tv",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            # Continuous preview timeline: each chunk's TS timestamps start at
            # its true global offset, so the growing playlist plays as one
            # stream (DISCONTINUITY tags cover the independent encodes).
            "-muxdelay", "0", "-muxpreload", "0",
            "-output_ts_offset", f"{a_start:.6f}",
            "-f", "hls",
            "-hls_time", "4",
            "-hls_list_size", "0",
            "-hls_playlist_type", "vod",
            "-hls_segment_type", "mpegts",
            "-hls_segment_filename", seg_pattern,
            chunk_pl,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=_TRANSCODE_TIMEOUT_S)
        if r.returncode != 0:
            raise RuntimeError(
                f"preview transcode of chunk {k} failed "
                f"(rc={r.returncode}): {(r.stderr or '')[-800:]}")

        if self._cancelled:
            raise _PublishCancelled(f"chunk {k} discarded post-transcode: cancelled")
        segments = self._parse_chunk_playlist(chunk_pl)
        if not segments:
            raise RuntimeError(
                f"preview transcode of chunk {k} produced no segments")

        # Upload ORDER LAW: every segment lands BEFORE the playlist that
        # references it — the manifest never points at a missing object.
        for (seg_name, _dur) in segments:
            local = os.path.join(self._out_dir, seg_name)
            extra = {"ContentType": _SEGMENT_CT, "CacheControl": _SEGMENT_CACHE}
            if self._transfer_config is not None:
                self._s3.upload_file(local, self._bucket,
                                     f"{self._preview_prefix}/{seg_name}",
                                     ExtraArgs=extra,
                                     Config=self._transfer_config)
            else:
                self._s3.upload_file(local, self._bucket,
                                     f"{self._preview_prefix}/{seg_name}",
                                     ExtraArgs=extra)

        with self._cond:
            self._groups.append(segments)
            self.segments_published += 1
        self._upload_playlists(final=False)
        self._persist_payload()
        print(f"[progressive] chunk {k} published in {time.time() - t0:.1f}s "
              f"({len(segments)} segment(s), frames "
              f"[{frame_start},{frame_end}), "
              f"{self.segments_published}/{self._n_chunks} chunks live)",
              flush=True)

    @staticmethod
    def _parse_chunk_playlist_text(text):
        """(filename, duration) pairs out of an ffmpeg-written media playlist."""
        segs = []
        pending_dur = None
        for line in (text or "").splitlines():
            line = line.strip()
            m = re.match(r"#EXTINF:([0-9.]+)", line)
            if m:
                pending_dur = float(m.group(1))
            elif line and not line.startswith("#") and pending_dur is not None:
                segs.append((os.path.basename(line), pending_dur))
                pending_dur = None
        return segs

    def _parse_chunk_playlist(self, path):
        with open(path) as f:
            return self._parse_chunk_playlist_text(f.read())

    def _upload_playlists(self, final):
        with self._cond:
            groups = [list(g) for g in self._groups]
        media = _render_media_playlist(groups, final=final)
        if not self._master_uploaded:
            self._s3.put_object(
                Bucket=self._bucket,
                Key=f"{self._preview_prefix}/master.m3u8",
                Body=_render_master_playlist().encode("utf-8"),
                ContentType=_PLAYLIST_CT, CacheControl=_PLAYLIST_CACHE)
            self._master_uploaded = True
        self._s3.put_object(
            Bucket=self._bucket,
            Key=f"{self._preview_prefix}/media.m3u8",
            Body=media.encode("utf-8"),
            ContentType=_PLAYLIST_CT, CacheControl=_PLAYLIST_CACHE)

    def _extract_first_frame(self, chunk_path):
        """Frame 1 of chunk 0 as a JPEG next to the preview prefix.
        Best-effort: a still-frame miss must never cost the preview."""
        try:
            local = os.path.join(self._work_dir, "preview_first_frame.jpg")
            r = subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-i", chunk_path,
                 "-frames:v", "1", "-q:v", "3", local],
                capture_output=True, text=True, timeout=60)
            if r.returncode != 0 or not os.path.exists(local):
                raise RuntimeError((r.stderr or "no output")[-300:])
            self._s3.upload_file(
                local, self._bucket,
                f"{self._preview_prefix}/first_frame.jpg",
                ExtraArgs={"ContentType": "image/jpeg",
                           "CacheControl": _SEGMENT_CACHE})
            self._first_frame_url = f"{self._preview_url_base}/first_frame.jpg"
        except Exception as fe:
            print(f"[progressive] first-frame extract failed (non-fatal): "
                  f"{type(fe).__name__}: {fe}", flush=True)
            self._first_frame_url = None

    def _persist_payload(self, superseded=False):
        """Phase B: hand the preview payload to the injected persist callback
        (handler._persist_preview — daemon, fail-open, terminal-fenced).
        Fail-open here too: a status-write miss never costs the preview.
        TERMINAL-STATE LAW (Zac ruling 1a): the payload carries `final` once
        ENDLIST is written and `superseded` on a terminal-seam cancel — a
        preview must never be servable as a terminal state; the client always
        swaps to the final artifact."""
        try:
            payload = {
                "preview_hls_url": self.preview_hls_url,
                "segments_published": int(self.segments_published),
                "plan_summary": self._plan_summary,
                "first_frame_url": self._first_frame_url,
                "final": bool(self.finalized),
                "superseded": bool(superseded),
            }
            self.last_payload = payload
            if self._persist_cb is not None:
                self._persist_cb(payload)
        except Exception as pe:
            print(f"[progressive] preview persist failed (fail open): "
                  f"{type(pe).__name__}: {pe}", flush=True)

    # ── Loud fallback ───────────────────────────────────────────────────────

    def _fail_locked(self, code, detail):
        """Caller holds self._cond."""
        if self.disabled:
            return
        self.disabled = True
        self._cond.notify_all()
        print(f"[progressive] PUBLISH FALLBACK ({code}): {detail} — preview "
              f"publishing DISABLED for this job; the render and standard "
              f"delivery are unaffected", flush=True)
        try:
            if self._divergence_cb is not None:
                self._divergence_cb(
                    "render",
                    {"stage": code, "detail": str(detail)[:300],
                     "job_id": self._job_id,
                     "published": int(self.segments_published)},
                    "progressive_publish_fallback",
                    reason=f"progressive_{code}")
        except Exception as de:  # divergence recording itself must not raise
            print(f"[progressive] divergence record failed: {de}", flush=True)

    def _fail(self, stage, err):
        try:
            with self._cond:
                self._fail_locked(stage, f"{type(err).__name__}: {err}")
        except Exception:  # absolute floor: never raise into the render
            pass
