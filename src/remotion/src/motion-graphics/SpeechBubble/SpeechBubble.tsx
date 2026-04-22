import React from "react";
import { IMessageBubble } from "./IMessageBubble";
import { InstagramComment } from "./InstagramComment";
import { TikTokComment } from "./TikTokComment";
import { TweetBubble } from "./TweetBubble";
import type { SpeechBubbleProps } from "./types";

export const SpeechBubble: React.FC<SpeechBubbleProps> = (props) => {
  switch (props.platform) {
    case "tweet":
      return <TweetBubble {...props} />;
    case "instagram":
      return <InstagramComment {...props} />;
    case "imessage":
      return <IMessageBubble {...props} />;
    case "tiktok":
      return <TikTokComment {...props} />;
  }
};
