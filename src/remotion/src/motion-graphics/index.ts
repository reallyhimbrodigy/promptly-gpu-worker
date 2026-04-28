export { useMGPhase, resolveMGPosition } from "./shared";
export type { MGTimingProps, MGPhaseState, MGPhase, MGPositionProps, MGAnchor } from "./shared";

// LowerThird kept here ONLY for the `lower_third` text_overlay variant
// to import; it is no longer a usable motion_graphic.
export { LowerThird } from "./LowerThird";
export type { LowerThirdProps } from "./LowerThird";
export { AnnotationArrow } from "./AnnotationArrow";
export type { AnnotationArrowProps } from "./AnnotationArrow";
export { QuoteCard } from "./QuoteCard";
export type { QuoteCardProps } from "./QuoteCard";
export { StatCard } from "./StatCard";
export type { StatCardProps } from "./StatCard";
export { Notification } from "./Notification";
export type { NotificationProps, NotificationApp, NotificationItem } from "./Notification";
export {
  SpeechBubble,
  TweetBubble,
  InstagramComment,
  IMessageBubble,
  TikTokComment,
} from "./SpeechBubble";
export type {
  SpeechBubbleProps,
  TweetBubbleProps,
  InstagramCommentProps,
  IMessageBubbleProps,
  TikTokCommentProps,
} from "./SpeechBubble";
export { ProgressBar } from "./ProgressBar";
export type {
  ProgressBarProps,
  ProgressBarValueProps,
  ProgressBarPercentProps,
  ProgressBarMilestone,
} from "./ProgressBar";
export { ChatThread } from "./ChatThread";
export type {
  ChatThreadProps,
  ChatMessage,
  ChatThreadHeader,
} from "./ChatThread";
export { TornPaper } from "./TornPaper";
export type { TornPaperProps } from "./TornPaper";
export { StickyNotes } from "./StickyNotes";
export type { StickyNotesProps, StickyNote } from "./StickyNotes";
export { Toggle } from "./Toggle";
export type { ToggleProps } from "./Toggle";
export { RecordingFrame } from "./RecordingFrame";
export type {
  RecordingFrameProps,
  RecordingFrameAnnotation,
} from "./RecordingFrame";
