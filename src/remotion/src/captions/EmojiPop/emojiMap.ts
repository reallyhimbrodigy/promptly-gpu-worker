/**
 * Keyword-only emoji mapping for Submagic-style captions.
 * 48 animated Lottie emojis from Google Noto Emoji.
 * Only impactful/special words trigger emojis.
 */

// ── Lottie imports ──
import alarmData from "./lottie/alarm.json";
import alienData from "./lottie/alien.json";
import bellData from "./lottie/bell.json";
import bombData from "./lottie/bomb.json";
import brainData from "./lottie/brain.json";
import checkmarkData from "./lottie/checkmark.json";
import coolData from "./lottie/cool.json";
import crossmarkData from "./lottie/crossmark.json";
import crownData from "./lottie/crown.json";
import cryingData from "./lottie/crying.json";
import devilData from "./lottie/devil.json";
import diamondData from "./lottie/diamond.json";
import explosionData from "./lottie/explosion.json";
import eyesData from "./lottie/eyes.json";
import fireData from "./lottie/fire.json";
import fistData from "./lottie/fist.json";
import ghostData from "./lottie/ghost.json";
import globeData from "./lottie/globe.json";
import handshakeData from "./lottie/handshake.json";
import heartData from "./lottie/heart.json";
import hearteyesData from "./lottie/hearteyes.json";
import hourglassData from "./lottie/hourglass.json";
import hundredData from "./lottie/hundred.json";
import kissData from "./lottie/kiss.json";
import lightbulbData from "./lottie/lightbulb.json";
import lightningData from "./lottie/lightning.json";
import loveyouData from "./lottie/loveyou.json";
import mindblownData from "./lottie/mindblown.json";
import moneywingsData from "./lottie/moneywings.json";
import muscleData from "./lottie/muscle.json";
import partyingData from "./lottie/partying.json";
import partypopperData from "./lottie/partypopper.json";
import prayData from "./lottie/pray.json";
import rageData from "./lottie/rage.json";
import rocketData from "./lottie/rocket.json";
import roflData from "./lottie/rofl.json";
import screamData from "./lottie/scream.json";
import shushingData from "./lottie/shushing.json";
import skullData from "./lottie/skull.json";
import sparklesData from "./lottie/sparkles.json";
import starData from "./lottie/star.json";
import starstruckData from "./lottie/starstruck.json";
import stopData from "./lottie/stop.json";
import surprisedData from "./lottie/surprised.json";
import targetData from "./lottie/target.json";
import thinkingData from "./lottie/thinking.json";
import thumbsupData from "./lottie/thumbsup.json";
import trophyData from "./lottie/trophy.json";

export interface LottieEmojiData {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  animationData: any;
  label: string;
}

// ── Registry ──

const E: Record<string, LottieEmojiData> = {
  alarm: { animationData: alarmData, label: "alarm" },
  alien: { animationData: alienData, label: "alien" },
  bell: { animationData: bellData, label: "bell" },
  bomb: { animationData: bombData, label: "bomb" },
  brain: { animationData: brainData, label: "brain" },
  checkmark: { animationData: checkmarkData, label: "checkmark" },
  cool: { animationData: coolData, label: "cool" },
  crossmark: { animationData: crossmarkData, label: "crossmark" },
  crown: { animationData: crownData, label: "crown" },
  crying: { animationData: cryingData, label: "crying" },
  devil: { animationData: devilData, label: "devil" },
  diamond: { animationData: diamondData, label: "diamond" },
  explosion: { animationData: explosionData, label: "explosion" },
  eyes: { animationData: eyesData, label: "eyes" },
  fire: { animationData: fireData, label: "fire" },
  fist: { animationData: fistData, label: "fist" },
  ghost: { animationData: ghostData, label: "ghost" },
  globe: { animationData: globeData, label: "globe" },
  handshake: { animationData: handshakeData, label: "handshake" },
  heart: { animationData: heartData, label: "heart" },
  hearteyes: { animationData: hearteyesData, label: "hearteyes" },
  hourglass: { animationData: hourglassData, label: "hourglass" },
  hundred: { animationData: hundredData, label: "hundred" },
  kiss: { animationData: kissData, label: "kiss" },
  lightbulb: { animationData: lightbulbData, label: "lightbulb" },
  lightning: { animationData: lightningData, label: "lightning" },
  loveyou: { animationData: loveyouData, label: "loveyou" },
  mindblown: { animationData: mindblownData, label: "mindblown" },
  moneywings: { animationData: moneywingsData, label: "moneywings" },
  muscle: { animationData: muscleData, label: "muscle" },
  partying: { animationData: partyingData, label: "partying" },
  partypopper: { animationData: partypopperData, label: "partypopper" },
  pray: { animationData: prayData, label: "pray" },
  rage: { animationData: rageData, label: "rage" },
  rocket: { animationData: rocketData, label: "rocket" },
  rofl: { animationData: roflData, label: "rofl" },
  scream: { animationData: screamData, label: "scream" },
  shushing: { animationData: shushingData, label: "shushing" },
  skull: { animationData: skullData, label: "skull" },
  sparkles: { animationData: sparklesData, label: "sparkles" },
  star: { animationData: starData, label: "star" },
  starstruck: { animationData: starstruckData, label: "starstruck" },
  stop: { animationData: stopData, label: "stop" },
  surprised: { animationData: surprisedData, label: "surprised" },
  target: { animationData: targetData, label: "target" },
  thinking: { animationData: thinkingData, label: "thinking" },
  thumbsup: { animationData: thumbsupData, label: "thumbsup" },
  trophy: { animationData: trophyData, label: "trophy" },
};

// ── Keyword → Emoji mapping ──

const KEYWORD_MAP: Record<string, string> = {
  // ─ Action / Motion ─
  stop: "stop",
  go: "rocket",
  run: "rocket",
  start: "rocket",
  launch: "rocket",
  fly: "rocket",
  build: "muscle",
  create: "sparkles",
  make: "sparkles",
  push: "muscle",
  pull: "muscle",
  grind: "fire",
  hustle: "fire",
  work: "muscle",
  fight: "fist",
  punch: "fist",
  hit: "fist",
  smash: "fist",
  crush: "explosion",
  destroy: "explosion",
  break: "explosion",
  explode: "explosion",
  blow: "explosion",
  crash: "explosion",
  kill: "skull",
  dead: "skull",
  die: "skull",
  execute: "lightning",
  move: "rocket",
  shake: "explosion",
  drop: "bomb",
  bomb: "bomb",

  // ─ Achievement / Success ─
  win: "trophy",
  won: "trophy",
  winner: "trophy",
  success: "trophy",
  champion: "trophy",
  victory: "trophy",
  top: "crown",
  first: "trophy",
  best: "trophy",
  greatest: "crown",
  legend: "crown",
  legendary: "crown",
  king: "crown",
  queen: "crown",
  boss: "crown",
  dominate: "crown",
  reign: "crown",
  rule: "crown",
  perfect: "hundred",
  hundred: "hundred",
  great: "star",
  amazing: "starstruck",
  incredible: "mindblown",
  insane: "mindblown",
  unbelievable: "mindblown",
  impossible: "mindblown",
  wow: "starstruck",
  awesome: "fire",
  epic: "fire",
  goat: "crown",
  elite: "diamond",
  premium: "diamond",

  // ─ Money / Wealth ─
  money: "moneywings",
  cash: "moneywings",
  rich: "moneywings",
  wealth: "moneywings",
  million: "moneywings",
  billion: "moneywings",
  profit: "moneywings",
  earn: "moneywings",
  paid: "moneywings",
  revenue: "moneywings",
  invest: "moneywings",
  business: "moneywings",
  diamond: "diamond",
  gold: "sparkles",
  luxury: "diamond",
  expensive: "diamond",

  // ─ Emotion: Positive ─
  love: "heart",
  heart: "heart",
  beautiful: "hearteyes",
  gorgeous: "hearteyes",
  pretty: "hearteyes",
  cute: "hearteyes",
  kiss: "kiss",
  happy: "partying",
  excited: "partypopper",
  celebrate: "partypopper",
  party: "partying",
  fun: "partying",
  joy: "partypopper",
  glad: "partying",
  thank: "pray",
  thanks: "pray",
  grateful: "pray",
  blessed: "pray",
  hope: "pray",
  please: "pray",
  yes: "checkmark",
  right: "checkmark",
  correct: "checkmark",
  true: "checkmark",
  agree: "thumbsup",
  good: "thumbsup",
  nice: "thumbsup",
  cool: "cool",
  chill: "cool",
  smooth: "cool",
  funny: "rofl",
  hilarious: "rofl",
  laugh: "rofl",
  lol: "rofl",
  joke: "rofl",

  // ─ Emotion: Negative ─
  hate: "rage",
  angry: "rage",
  mad: "rage",
  furious: "rage",
  rage: "rage",
  pissed: "rage",
  sad: "crying",
  cry: "crying",
  crying: "crying",
  tears: "crying",
  pain: "crying",
  hurt: "crying",
  depressed: "crying",
  fear: "scream",
  scared: "scream",
  terrified: "scream",
  horror: "scream",
  scary: "scream",
  creepy: "ghost",
  haunted: "ghost",
  spooky: "ghost",
  evil: "devil",
  wicked: "devil",
  dark: "devil",
  demon: "devil",
  hell: "devil",
  no: "crossmark",
  wrong: "crossmark",
  false: "crossmark",
  never: "crossmark",
  fail: "crossmark",
  failed: "crossmark",
  lost: "crying",
  lose: "crying",

  // ─ Surprise / Shock ─
  crazy: "mindblown",
  wild: "mindblown",
  shocked: "surprised",
  surprise: "surprised",
  surprised: "surprised",
  what: "surprised",
  whoa: "mindblown",
  omg: "mindblown",
  wtf: "mindblown",
  weird: "alien",
  strange: "alien",
  alien: "alien",

  // ─ Mind / Knowledge ─
  brain: "brain",
  think: "thinking",
  thinking: "thinking",
  thought: "thinking",
  smart: "brain",
  genius: "brain",
  clever: "brain",
  mind: "brain",
  idea: "lightbulb",
  realize: "lightbulb",
  understand: "lightbulb",
  learn: "brain",
  knowledge: "brain",
  focus: "target",
  aim: "target",
  goal: "target",
  mission: "target",
  strategy: "target",
  plan: "target",
  secret: "shushing",
  quiet: "shushing",
  shhh: "shushing",
  whisper: "shushing",
  hidden: "shushing",

  // ─ Energy / Power ─
  fire: "fire",
  burn: "fire",
  hot: "fire",
  lit: "fire",
  flame: "fire",
  heat: "fire",
  energy: "lightning",
  power: "lightning",
  electric: "lightning",
  fast: "lightning",
  quick: "lightning",
  speed: "lightning",
  now: "lightning",
  strong: "muscle",
  strength: "muscle",
  powerful: "muscle",
  tough: "muscle",
  hard: "muscle",
  beast: "muscle",
  warrior: "muscle",
  fierce: "fire",
  intense: "fire",
  savage: "skull",
  brutal: "skull",

  // ─ Time ─
  waiting: "hourglass",
  wait: "hourglass",
  time: "hourglass",
  clock: "alarm",
  deadline: "alarm",
  urgent: "alarm",
  hurry: "alarm",
  late: "alarm",
  early: "alarm",
  future: "rocket",
  forever: "sparkles",

  // ─ People / Social ─
  nobody: "eyes",
  everyone: "globe",
  people: "globe",
  world: "globe",
  global: "globe",
  earth: "globe",
  together: "handshake",
  deal: "handshake",
  partner: "handshake",
  team: "handshake",
  friend: "loveyou",
  family: "heart",
  watch: "eyes",
  look: "eyes",
  see: "eyes",
  attention: "bell",
  listen: "bell",
  hear: "bell",
  announce: "bell",
  alert: "bell",

  // ─ Positive intensifiers ─
  all: "hundred",
  every: "hundred",
  totally: "hundred",
  absolutely: "hundred",
  completely: "hundred",
  real: "hundred",
  literally: "hundred",

  // ─ Body / Action ─
  save: "pray",
  coming: "eyes",
  permission: "stop",
  dream: "sparkles",
  magic: "sparkles",
  shine: "sparkles",
  glow: "sparkles",
  star: "star",
  famous: "star",
  viral: "rocket",
  trending: "fire",
};

/**
 * Get Lottie animation data for a keyword.
 * Returns null for non-keywords (common words).
 */
export function getEmojiForKeyword(word: string): LottieEmojiData | null {
  const key = word.toLowerCase().replace(/[^a-z]/g, "");
  const emojiKey = KEYWORD_MAP[key];
  if (!emojiKey) return null;
  return E[emojiKey] ?? null;
}
