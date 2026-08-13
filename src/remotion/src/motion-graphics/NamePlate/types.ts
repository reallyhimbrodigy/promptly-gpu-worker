import type { MGTimingProps } from "../shared/types";

// [§3.1 component D] The name-plate — REF-1 opens with "Jaden Koh /
// Separation Manager" over the speaker's first seconds. It is the cheapest
// credibility signal in the reference set: it tells the viewer WHO is talking
// before they decide whether to keep watching.
//
// Deliberately NOT a lower-third "template": the content (name, role, accent)
// is generated per video, and the component is the tool [§4.2]. Two corporate
// promos produce two different plates.
export interface NamePlateProps extends MGTimingProps {
  // The person. Required — a plate with no name has no purpose.
  name: string;
  // Role / title / company line. Optional: not every speaker has one.
  role?: string;
  // Rule + role colour. Comes from the edit's locked palette, never hardcoded.
  accentColor?: string;   // default "#F5A11E"
  nameColor?: string;     // default "#FFFFFF"
  // Which third the plate sits in. Resolved to pixels by the renderer against
  // the canvas's own safe zones, so this is correct on landscape too.
  anchor?: "lower_third_safe" | "upper_third_safe";
  // Frame fraction the plate's text block occupies. Default 0.42.
  widthPct?: number;
}
