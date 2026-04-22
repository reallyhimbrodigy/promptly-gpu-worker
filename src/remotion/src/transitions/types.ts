import type { CSSProperties } from "react";

/**
 * Transition base props for the Promptly fork.
 *
 * The original pack transitions took clipA/clipB as string URLs and always
 * played the video from frame 0 at 1x speed. In Promptly's single-source
 * pipeline every clip is a seek + speed-warp of the ONE source video file,
 * so every transition must seek and speed-adjust both sides independently.
 *
 * startFromA / startFromB are in source FRAMES (not seconds).
 * playbackRateA / playbackRateB are scalar speed multipliers (0.25 – 4).
 */
export interface TransitionProps {
  clipA: string;
  clipB: string;
  progress: number;
  style?: CSSProperties;
  startFromA?: number;
  startFromB?: number;
  playbackRateA?: number;
  playbackRateB?: number;
}

export interface CardSwipeProps extends TransitionProps {
  direction?: "left" | "right";
}

export interface ZoomThroughProps extends TransitionProps {}

export interface SlideOverProps extends TransitionProps {
  direction?: "left" | "right";
}

export interface StackProps extends TransitionProps {}

export interface CrossfadeZoomProps extends TransitionProps {}

export interface ShutterFlashProps extends TransitionProps {
  blades?: "single" | "dual";
  flashColor?: string;
  bladeColor?: string;
  chromaticAberrationOnReveal?: boolean;
}

export interface LightLeakProps extends TransitionProps {
  palette?: "warm" | "gold" | "cool" | "magenta";
  direction?: "tl-br" | "tr-bl" | "left-right" | "top-down";
  intensity?: number;
}

export interface StepPushProps extends TransitionProps {
  direction?: "left" | "right" | "up" | "down";
  separatorShadow?: boolean;
}

export interface NewspaperWipeProps extends TransitionProps {
  assetPath?: string;
}

export interface FilmStripProps extends TransitionProps {
  frameBackground?: string;
  caption?: string;
  showBookmark?: boolean;
  showGrid?: boolean;
  advanceFrames?: number;
}

export interface SceneTitleProps extends TransitionProps {
  title: string;
  label?: string;
  variant?: "full" | "half-top" | "half-bottom";
  theme?: "dark" | "light";
  accentColor?: string;
  titleColor?: string;
  labelColor?: string;
  showDivider?: boolean;
}
