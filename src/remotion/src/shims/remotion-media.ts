// Build-time alias target for `@remotion/media`. The five ABE.zip zoom
// components that import `Video` from `@remotion/media` get this shim's
// `Video` instead — a thin re-export of `OffthreadVideo` from remotion
// core.
//
// Why: the ABE components hand the Video element a CSS transform that
// changes per frame via React rerenders. @remotion/media's Video routes
// frames through WebCodecs (chrome's VideoDecoder API). On short pre-
// extracted clips the WebCodecs path was timing out at frame 1-3 with
// "Timeout while extracting frame at time Nsec". OffthreadVideo uses
// Chromium's standard HTMLVideoElement + frame capture, which decodes
// every frame the components ask for without the WebCodecs round trip.
//
// The component files themselves remain byte-identical to the ABE.zip
// originals — the redirect happens entirely in the webpack resolve
// stage at prebundle time.
export { OffthreadVideo as Video } from "remotion";
