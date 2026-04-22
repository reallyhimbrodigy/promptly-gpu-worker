import type { MGTimingProps } from "../shared/types";

export interface RecordingFrameAnnotation {
  // Small muted label (e.g. "ELAPSED", "WORDS", "RATE", "SIG").
  label: string;
  // Main value. Special values drive live counters:
  //   "timestamp" → live `T+N.Ns` counter from the component start
  //   "wordcount" → ticking integer (~2/sec, natural speech pace)
  //   "wpm"       → settles in the ~160–200 range as time elapses
  // Anything else renders as-is.
  value: "timestamp" | "wordcount" | "wpm" | string;
  // Which corner to place the annotation in.
  corner: "top-left" | "top-right" | "bottom-left" | "bottom-right";
}

export interface RecordingFrameProps extends MGTimingProps {
  // Accent color for live value readouts. Default "#C5432E".
  accentColor?: string;
  // Muted label color. Default "#F0EEE9".
  textColor?: string;
  // Annotation value font size. Labels render at 0.75x this. Default 24.
  annotationFontSize?: number;
  // Thin inset border. Default true.
  showFrame?: boolean;
  // Border color. Default "rgba(240,238,233,0.08)".
  frameBorderColor?: string;
  // Horizontal scan line cycling down the frame. Default true.
  showScanLine?: boolean;
  // Scan line color. Default "rgba(197,67,46,0.4)".
  scanLineColor?: string;
  // Frames per scan cycle. Default 90.
  scanLineCycle?: number;
  // Corner annotations. Defaults to ELAPSED / WORDS / RATE / SIG —
  // matches the original Telemetry frame 1:1.
  annotations?: RecordingFrameAnnotation[];
}
