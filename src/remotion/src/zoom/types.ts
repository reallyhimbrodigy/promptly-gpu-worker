import type { CSSProperties } from "react";

export interface ZoomEvent {
  // When the zoom begins (ms from composition start).
  startMs: number;
  // How long the zoom lasts (ms). Includes ramp-in, hold, and ramp-out.
  durationMs: number;
  // Target scale factor (default varies per effect, typically 1.2–1.35).
  scale?: number;
  // Horizontal origin 0–1 (default: 0.5 = center).
  originX?: number;
  // Vertical origin 0–1 (default: 0.5 = center).
  originY?: number;
}

export interface BaseZoomProps {
  // Video source URL or staticFile() path.
  src: string;
  // Array of zoom events. Each effect handles ramp-in/hold/ramp-out internally.
  // Pass an empty array for full-duration mode (effect spans entire composition).
  events: ZoomEvent[];
  // Optional style override on the outer container.
  style?: CSSProperties;
  // Source frames to skip before playback starts (Promptly fork).
  startFrom?: number;
  // Playback speed multiplier, 0.25–4 (Promptly fork).
  playbackRate?: number;
}

export interface SmoothPushProps extends BaseZoomProps {}

export interface SnapReframeProps extends BaseZoomProps {}

export interface FocusWindowProps extends BaseZoomProps {
  // Size of the inner window as a fraction of the frame. Default 0.72.
  windowScale?: number;
  // Border width in px. Default 0 (no border).
  borderWidth?: number;
  // Border color. Default "transparent".
  borderColor?: string;
  // How much the background is zoomed in. Default 1.8.
  bgScale?: number;
}

export interface StepZoomProps extends BaseZoomProps {}

export interface LetterboxPushProps extends BaseZoomProps {
  // Maximum bar height as fraction of frame height. Default 0.12.
  maxBarHeight?: number;
}

export interface StageZoomProps extends BaseZoomProps {
  // Scale for first stage. Default 1.15.
  firstStage?: number;
  // Scale for second stage. Default 1.35.
  secondStage?: number;
}

export interface DepthPullProps extends BaseZoomProps {
  // Edge blur max in px. Default 4.
  edgeBlur?: number;
  // Show decorative frame lines. Default true.
  frameLines?: boolean;
}
