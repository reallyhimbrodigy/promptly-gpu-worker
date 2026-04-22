import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface ChatMessage {
  // "me" → outgoing (right-aligned blue bubble).
  // "them" → incoming (left-aligned grey bubble).
  sender: "me" | "them";
  text: string;
  // Duration of the typing indicator BEFORE this message pops in.
  // Defaults: 900ms for "them", 0 for "me" (we don't show ourselves typing).
  typingMs?: number;
  // Pause AFTER this message settles before the next starts. Default 450ms.
  holdMs?: number;
}

export interface ChatThreadHeader {
  // Contact name (bold, centered in the iMessage profile header).
  name: string;
  // Small subtitle under the name (default "iMessage").
  subtitle?: string;
  // Optional avatar URL. If omitted, `initials` is rendered in a colored circle.
  avatarSrc?: string;
  initials?: string;
  avatarColor?: string;
}

export interface ChatThreadProps extends MGTimingProps, MGPositionProps {
  // Header at the top of the chat (iMessage profile view).
  header?: ChatThreadHeader;
  // Messages rendered in order. Each lands sequentially; the typing indicator
  // plays on the correct side between messages.
  messages: ChatMessage[];
  // Card width in pixels. Default 820 (≈76% of 1080 frame — matches how
  // screenshot cards sit in real Hormozi/Gadzhi-style creator content).
  width?: number;
  // Card minimum height. Default 1320 (~phone-screen aspect ratio).
  minHeight?: number;
  // Card corner radius. Default 56 (iPhone hardware corner feel).
  borderRadius?: number;
  // Clock shown in the iOS status bar. Default "9:41".
  statusBarTime?: string;
  // Show the iOS status bar (time + signal/wifi/battery). Default true.
  showStatusBar?: boolean;
  // Show the bottom home indicator pill. Default true.
  showHomeIndicator?: boolean;
  // Background. Default "#000000" (iMessage dark mode).
  backgroundColor?: string;
  // Incoming bubble color. Default "#26252A".
  incomingColor?: string;
  incomingTextColor?: string;
  // Outgoing bubble color. Default iMessage blue "#0A84FF".
  outgoingColor?: string;
  outgoingTextColor?: string;
}
