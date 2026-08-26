import type { MGTimingProps } from "../shared/types";

// [ART_DIRECTION §6] The COPY-FREE close.
//
// Every other end-card kind (cta / logo_sting / social) needs words, and words
// need the speaker to have said an identity out loud. MEASURED on 854
// production transcripts: any headline source at all is 2.2%. So the
// copy-bearing card cannot be the universal close — it is the same ~2%
// population as the name plate.
//
// This one carries NO TEXT. It is the edit's own final seconds resolving into
// the job's palette, so the video ENDS rather than stops. There is nothing here
// to fabricate, which is exactly why it reaches everyone.
export interface EchoOutroProps extends MGTimingProps {
  // The job's accent, laid over the footage. From the design system built off
  // this user's own frames — never a constant, same law as every other brand
  // component.
  tint: string;
  // How strongly the tint sits over the picture. Low by construction: this is
  // a resolution, not a curtain.
  tintOpacity?: number;
  vignette?: boolean;
  // The palette's foreground, used for the closing rule.
  rule?: string;
}
