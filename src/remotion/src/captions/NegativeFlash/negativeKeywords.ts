/**
 * Keywords that trigger the negative/invert effect.
 */

const NEGATIVE_KEYWORDS = new Set([
  // Action
  "stop", "go", "run", "start", "launch", "build", "create", "push",
  "grind", "hustle", "fight", "crush", "destroy", "break", "kill",
  "execute", "move", "drop", "smash", "explode",

  // Achievement
  "win", "won", "winner", "success", "champion", "victory", "best",
  "greatest", "legend", "legendary", "king", "queen", "boss",
  "perfect", "amazing", "incredible", "insane", "epic", "goat", "elite",

  // Money
  "money", "cash", "rich", "wealth", "million", "billion", "profit",
  "paid", "revenue", "business", "diamond", "gold", "luxury",

  // Emotion
  "love", "hate", "crazy", "wild", "savage", "brutal", "fierce",
  "scared", "fear", "evil", "hell",

  // Energy
  "fire", "burn", "hot", "lit", "power", "energy", "electric",
  "fast", "strong", "powerful", "beast", "warrior",

  // Mind
  "brain", "think", "smart", "genius", "mind", "idea", "focus",
  "secret",

  // Impact
  "dream", "magic", "star", "famous", "viral", "trending",
  "world", "forever", "never", "always", "everything", "nothing",
  "truth", "real", "fake", "dead", "die", "live", "life",

  // Emphasis
  "attention", "listen", "watch", "look", "believe", "imagine",
  "remember", "forget", "impossible", "unstoppable",
]);

export function isNegativeKeyword(word: string): boolean {
  const key = word.toLowerCase().replace(/[^a-z]/g, "");
  return NEGATIVE_KEYWORDS.has(key);
}
