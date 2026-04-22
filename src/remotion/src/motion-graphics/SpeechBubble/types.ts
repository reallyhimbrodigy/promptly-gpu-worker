import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

// ---------------------------------------------------------------------------
// SpeechBubble — social-platform comment/message mocks.
//
// A SpeechBubble is a per-platform visual simulacrum of a real social post,
// tuned tightly enough to the source platform (Twitter/X, Instagram, iMessage,
// TikTok) that a viewer recognizes it before they consciously notice it's
// a motion graphic.
// ---------------------------------------------------------------------------

// Props common to all variants.
interface BaseProps extends MGTimingProps, MGPositionProps {
  // Card width in pixels. Default 620.
  width?: number;
}

// -- Twitter / X ------------------------------------------------------------
export interface TweetBubbleProps extends BaseProps {
  platform: "tweet";
  avatarSrc?: string;
  initials?: string;
  avatarColor?: string;
  name: string;
  // Handle. The "@" and the "· timestamp" suffix are added by the component
  // where appropriate — callers pass in whatever string they want rendered
  // in the handle slot (e.g. "@naval" or "@naval · 2h").
  handle: string;
  timestamp?: string;
  verified?: boolean;
  text: string;
  stats: { replies: number; reposts: number; likes: number; views: number };
  darkMode?: boolean;
}

// -- Instagram --------------------------------------------------------------
export interface InstagramCommentProps extends BaseProps {
  platform: "instagram";
  avatarSrc?: string;
  initials?: string;
  avatarColor?: string;
  username: string;
  comment: string;
  timestamp: string;
  likes?: number;
}

// -- iMessage ---------------------------------------------------------------
export interface IMessageBubbleProps extends BaseProps {
  platform: "imessage";
  messageType: "incoming" | "outgoing";
  text: string;
  status?: "Delivered" | "Read";
  typewriter?: boolean;
}

// -- TikTok -----------------------------------------------------------------
export interface TikTokCommentProps extends BaseProps {
  platform: "tiktok";
  avatarSrc?: string;
  initials?: string;
  avatarColor?: string;
  username: string;
  comment: string;
  likes: number;
}

// Discriminated union consumed by the top-level dispatcher.
export type SpeechBubbleProps =
  | TweetBubbleProps
  | InstagramCommentProps
  | IMessageBubbleProps
  | TikTokCommentProps;
