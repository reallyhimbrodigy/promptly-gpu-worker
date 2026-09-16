# ChatCut's tool surface, read from `tools/list` on 2026-09-15

NOT from their docs and not inferred. Every line below came back from the
hosted external-MCP endpoint this lane authenticates against
(`https://api.chatcut.io/api/external-mcp/mcp`), via `tools/list`.

**60 tools. ZERO declare an `outputSchema`** — so what a tool returns is
knowable only from its prose and from calling it.

## What reaches the agent

| count | what comes back |
|---|---|
| 39 | TEXT/JSON |
| 17 | TEXT plus a URL or a job id — the bytes are elsewhere |
| 4 | TEXT plus IMAGES (`preview_timeline`, `inspect_asset`, `show_preview`, `web_browser`) |

## The three questions, answered by calling the surface

### 1. Does any tool return AUDIO, in any form?

**No.** Seven tools are ABOUT audio and every one returns JSON describing
what changed, or a URL:

- `detach_audio` — Detach a video clip's sound into a standalone audio item on an audio track (like "Detach Audio" in desktop NLEs).
- `smooth_audio` — One-shot polish pass over the ACTIVE timeline's audio: every touching audio cut gets a short centered audio crossfade (`builtin:tr-audio-cross-fade`, 
- `isolate_voice` — Apply or clear AI voice isolation on a video or audio item with spoken human voice.
- `submit_sound` — Generate a new sound effect with ElevenLabs and create an audio asset in the project library.
- `submit_music` — Submit an instrumental or vocal music generation job and create an audio asset in the project library.
- `submit_voice` — Submit a final TTS generation job.
- `manage_custom_voice` — List the current user's cloned voices, preflight creation access, create a Fish Audio voice clone from an uploaded project audio asset, apply one to t

`submit_export` accepts `format: "audio"` and renders a downloadable file.
`browse_assets` reports "concise transcript/generation/audio facts" —
loudness in LUFS, channel count, sample rate. No waveform, no levels, no
spectrogram, and nothing an agent can listen to.

### 2. Does any tool return MOTION — a segment, a GIF, a sequence?

**No, and they say so.** `preview_timeline`, verbatim:

> Uniform sampling only shows sampled moments, not continuous playback.

Video exists as FILES BEHIND URLS, never as something returned:

- `convert_motion_graphic_to_video` — Convert a motion graphic into a real, transparent video asset (vp8/WebM alpha).
- `export_motion_graphic_prores` — Export one or more motion graphics as transparent ProRes 4444 .mov renders.
- `submit_export` — Export the timeline as video, audio, subtitles, NLE XML, or an archive (NLE XML zipped with the timeline's media so clips relink automatically).
- `track_export` — Inspect cloud export/render jobs for the current project.
- `request_asset_download` — Create a user-facing download target for a project media asset.

### 3. The door that exists and is not on this surface

`request_asset_download` names it, verbatim:

> This is different from pull_asset: **pull_asset downloads bytes into the
> agent sandbox for analysis**, while request_asset_download gives the user
> an authenticated ChatCut download URL/path for their device.

`pull_asset` and `push_asset` are named in the descriptions of tools on this
surface and are **absent from the 60**. Byte-level access to a source is a
real ChatCut capability — on Desktop / the backend agent, not on the hosted
connector this lane uses.

## A live constraint in our code, read from a stale surface

`preview_timeline` now takes `viewerFrames` maxItems **25** and
`viewerFrameCount` max **25**. `chatcut_job_app.py` carries
`EDIT_FRAMES_N = 9` with the comment "preview_timeline returns at most 9" —
true when written, a 2.8x under-ask now.

## Every tool, and what comes back

| tool | returns | first line of its own description |
|---|---|---|
| `apply_script` | TEXT/JSON | Apply the edits already authored as `timeline.md` to the canonical timeline. |
| `ask_followup_questions` | TEXT/JSON | Ask the user follow-up questions in an interactive ChatCut card inside the MCP host chat. |
| `browse_assets` | TEXT/JSON | Browse lightweight source-asset cards in the current project's media pool. |
| `browse_library` | TEXT/JSON | Browse the ChatCut Library with one unified discovery tool. |
| `clean_script` | TEXT/JSON | Mechanical first-pass cleanup for talking-head transcripts already on the timeline: fixed filler-token removal plus batch silence pause compression /  |
| `convert_motion_graphic_to_video` | TEXT + URL/jobId | Convert a motion graphic into a real, transparent video asset (vp8/WebM alpha). |
| `create_motion_graphic_from_code` | TEXT/JSON | Create a new Motion Graphic asset from inline React/JSX code supplied in this tool call. |
| `create_project` | TEXT + URL/jobId | Create a new empty ChatCut project for the current external MCP user. |
| `delete_project` | TEXT/JSON | Soft-delete a ChatCut project the signed-in user owns — the same delete the editor dashboard performs. |
| `detach_audio` | TEXT/JSON | Detach a video clip's sound into a standalone audio item on an audio track (like "Detach Audio" in desktop NLEs). |
| `duplicate_project` | TEXT + URL/jobId | Duplicate an existing ChatCut project into a new project owned by the signed-in user — the same full copy the editor dashboard's Duplicate action make |
| `edit_asset` | TEXT/JSON | Update or delete a library asset. |
| `edit_captions` | TEXT/JSON | Manage captions/subtitles through an SRT-like, time-ordered Card model. |
| `edit_item` | TEXT/JSON | Item-level timeline operations across types: `video` (incl. |
| `edit_project` | TEXT/JSON | Update project-level settings or speakers. |
| `edit_track` | TEXT/JSON | Manage tracks. |
| `export_motion_graphic_prores` | TEXT + URL/jobId | Export one or more motion graphics as transparent ProRes 4444 .mov renders. |
| `find_transcript` | TEXT/JSON | Find the **timestamp** of a spoken phrase — a time-coordinate lookup, not a transcript reader or editing tool. |
| `get_editor_url` | TEXT + URL/jobId | Return the targeted ChatCut project's editor URL for the host's browser/card UI. |
| `import_media` | TEXT/JSON | Create a short local-helper import session for direct ChatCut media imports from bytes held by the external MCP client. |
| `inspect_asset` | TEXT + IMAGES | Inspect exactly one project source asset. |
| `inspect_item` | TEXT/JSON | Return complete readable detail for exactly one item already placed on a timeline. |
| `isolate_voice` | TEXT/JSON | Apply or clear AI voice isolation on a video or audio item with spoken human voice. |
| `list_projects` | TEXT + URL/jobId | List the ChatCut projects this signed-in user owns or can access, newest first. |
| `manage_avatar` | TEXT/JSON | Read live AI-avatar capabilities, official avatars, saved avatars, and provider-neutral voice choices; create, revise, import, inspect, or delete an a |
| `manage_custom_voice` | TEXT + URL/jobId | List the current user's cloned voices, preflight creation access, create a Fish Audio voice clone from an uploaded project audio asset, apply one to t |
| `manage_design_style` | TEXT/JSON | Manage the user's library of Design Styles. |
| `manage_markers` | TEXT/JSON | Manage note markers on a timeline. |
| `manage_media_pool` | TEXT/JSON | Organize the media pool library using user-managed folders. |
| `manage_skill` | TEXT/JSON | Manage reusable ChatCut workflow skills. |
| `manage_template` | TEXT/JSON | Manage editor templates for the current project. |
| `manage_timelines` | TEXT/JSON | Manage the project's timelines (sequences). |
| `manage_transcript` | TEXT/JSON | Manage source transcript fixes and deprecated low-level transcript variant inspection. |
| `manage_voice` | TEXT/JSON | Use one unified voice surface for official ChatCut voices and the current user's cloned voices. |
| `preview_timeline` | TEXT + IMAGES | Preview one timeline through independently selectable views of its structure, composed viewer frames, and bounded transcript. |
| `read_captions` | TEXT/JSON | Read captions as an SRT-like, time-ordered list of viewer-facing Cards. |
| `read_project` | TEXT/JSON | Return the lightweight map of the current project: project identity and settings, active timeline summary, timeline directory, and source-asset counts |
| `read_script` | TEXT/JSON | Script is the editing surface for transcript-based editing: use it whenever the spoken transcript or meaning decides what should play, be removed, be  |
| `register_converted_video` | TEXT/JSON | Import a finished MG→video render as a video asset in the media pool. |
| `report_user_friction` | TEXT/JSON | Silent backend telemetry. |
| `request_asset_download` | TEXT + URL/jobId | Create a user-facing download target for a project media asset. |
| `restore_project` | TEXT/JSON | Restore a soft-deleted ChatCut project (undo delete_project or a dashboard delete) for the signed-in owner. |
| `search_fonts` | TEXT/JSON | Search the font catalog that the cloud video renderer can load (Google Fonts library + project-bundled custom fonts). |
| `search_stock_media` | TEXT/JSON | Search curated public stock-media platforms for B-roll, photos, sounds, and music. |
| `show_preview` | TEXT + IMAGES | Open the embedded ChatCut widget in-document in this chat. |
| `smooth_audio` | TEXT/JSON | One-shot polish pass over the ACTIVE timeline's audio: every touching audio cut gets a short centered audio crossfade (`builtin:tr-audio-cross-fade`,  |
| `split_item` | TEXT/JSON | Cut one or more timeline items at given frame positions. |
| `submit_avatar_video` | TEXT + URL/jobId | Submit a final AI-avatar video generation batch and create video assets in the current project library. |
| `submit_export` | TEXT + URL/jobId | Export the timeline as video, audio, subtitles, NLE XML, or an archive (NLE XML zipped with the timeline's media so clips relink automatically). |
| `submit_music` | TEXT + URL/jobId | Submit an instrumental or vocal music generation job and create an audio asset in the project library. |
| `submit_shader` | TEXT + URL/jobId | Submit a shader generation job to the backend. |
| `submit_sound` | TEXT + URL/jobId | Generate a new sound effect with ElevenLabs and create an audio asset in the project library. |
| `submit_video` | TEXT + URL/jobId | Submit a video generation job and create a video asset in the project library. |
| `submit_video_translation` | TEXT + URL/jobId | Translate the spoken language of an existing project video into another language: translated dubbing that preserves the original voice character, opti |
| `submit_voice` | TEXT + URL/jobId | Submit a final TTS generation job. |
| `target_project` | TEXT/JSON | Bind this external MCP session to an existing ChatCut project. |
| `track_export` | TEXT + URL/jobId | Inspect cloud export/render jobs for the current project. |
| `track_progress` | TEXT/JSON | Manage long-running work in the editor. |
| `trigger_transcript` | TEXT/JSON | Start transcription for one audio or video asset when its transcription state is idle or error. |
| `web_browser` | TEXT + IMAGES | Scrape a web page via Firecrawl. |

## Three probes, CALLED — 2026-09-16

Not read from descriptions. Each of these is what came back.

### `get_more_tools` — not on this surface

```
MCP error -32602: Tool get_more_tools not found
```

### `web_browser` — a page scraper, and it refuses media

Pointed at a source `.mp4`, verbatim:

```
Firecrawl request failed (HTTP 500)
{"success":false,"code":"SCRAPE_UNSUPPORTED_FILE_ERROR",
 "error":"The URL returned a file type that Firecrawl cannot process:
 video/mp4. Firecrawl supports HTML web pages, PDFs, and common document
 formats. Raster images (PNG, JPEG, JPEG 2000, TIFF, GIF, BMP, WebP, AVIF)
 are OCR'd when the parsers option includes \"image\" ... Other binary files
 like vid[eo]"}
```

Its `formats` enum carries an undocumented `videos` member. Called with it,
it returns **an array of video URLs found on the page** — links, not video:

```
"javascriptReturns": [{"type":"object","value":[
  "https://cdn.chatcut.dev/playback/talking-head-final.mp4",
  "https://chatcut.io/best-moments/ai-editing/final-clip.mp4", ...]}]
```

So `web_browser` cannot reach an asset and does not return motion. It finds
URLs to files it cannot open.

### `request_asset_download` — a real URL, and it is not ours to open

The return, verbatim:

```json
{
  "success": true,
  "assetId": "07ccc1fc-b343-451f-8f6d-2fa46918745c",
  "contentType": "video/mp4",
  "downloadPath": "/api/assets/07ccc1fc-.../download?projectId=74036980-...",
  "downloadUrl": "https://api.chatcut.io/api/assets/07ccc1fc-.../download?projectId=74036980-...",
  "filename": "v09044g40000cm9oa7nog65s2crhkf00.mp4",
  "sizeKb": 3963,
  "type": "video",
  "variant": "source",
  "instruction": "Give the user the authenticated downloadUrl or downloadPath.
                  Do not call pull_asset for a user download; pull_asset is
                  sandbox-only. Do not expose raw storage URLs."
}
```

**It is a genuine URL to the source file — and it returns 401 to the harness,
with the MCP bearer token and without it.** Tested from a container holding a
valid grant:

```
no_auth  HTTP Error 401: Unauthorized
bearer   HTTP Error 401: Unauthorized
```

It is a user-facing door, authenticated against something the connector does
not hold, exactly as its own `instruction` says. The hopeful reading — a URL
the agent can fetch means the harness can fetch it — is wrong here, and only
calling it showed that.

**The answer to "is there byte-level access" is `pull_asset`, by their own
words "sandbox-only", and it is not on this surface.**
