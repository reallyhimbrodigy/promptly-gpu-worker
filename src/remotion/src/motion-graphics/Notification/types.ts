import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

// Supported app identifiers for the notification's icon slot.
export type NotificationApp =
  | "apple-pay"
  | "venmo"
  | "stripe"
  | "imessage"
  | "instagram"
  | "email"
  | "bank";

// A single notification entry. Stack 1-3 of these in the `notifications` prop.
export interface NotificationItem {
  // Which app icon + style to render.
  app: NotificationApp;
  // App name shown on the top row, left side (e.g. "Apple Pay").
  appName: string;
  // Timestamp shown on the top row, right side. Defaults to "now".
  timestamp?: string;
  // Headline text (e.g. "Payment Received").
  title: string;
  // Supporting body text. Truncates at 2 lines.
  body: string;
}

export interface NotificationProps extends MGTimingProps, MGPositionProps {
  // Controls the platform-specific visual language (default "ios").
  platform?: "ios" | "android";
  // 1-3 notifications to stack vertically. Each drops in sequentially; the
  // whole stack fades + slides up on exit.
  notifications: NotificationItem[];
}
