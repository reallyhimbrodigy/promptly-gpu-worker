// MULTILINGUAL A2.2 — caption direction detection. The first strong-directional
// LETTER decides (Unicode paragraph direction). Run: `node direction.test.ts`.
import { captionDirection, pagesDirection } from "./direction.ts";

let pass = 0;
const fails: string[] = [];
function check(name: string, cond: boolean, detail = "") {
  if (cond) pass++;
  else fails.push(name + (detail ? ` :: ${detail}` : ""));
  console.log(`  ${cond ? "PASS" : "FAIL"}  ${name}`);
}

// The exact contact-sheet strings: the three RTL cases must classify rtl, and
// every LTR case (including CJK, Thai, Devanagari, emoji-bearing, control) ltr.
check("arabic joining -> rtl", captionDirection("بِسْمِ اللَّه") === "rtl");
check("arabic lam-alef -> rtl", captionDirection("لا إلا") === "rtl");
check("hebrew niqqud -> rtl", captionDirection("שָׁלוֹם עוֹלָם") === "rtl");
check("devanagari conjunct -> ltr", captionDirection("क्षत्रिय त्रिशूल") === "ltr");
check("thai stacked -> ltr", captionDirection("ที่นี่ ปัญหา") === "ltr");
check("cjk+latin -> ltr", captionDirection("AI技術で 日本語") === "ltr");
check("latin control -> ltr", captionDirection("DOWNLOAD PROMPTLY") === "ltr");

// Direction-neutral leaders are skipped: the first strong LETTER wins, not the
// first character. UGC captions open with emoji, digits, hashtags constantly.
check("emoji-led ltr word -> ltr", captionDirection("🔥 let's go") === "ltr");
check("emoji-led arabic -> rtl", captionDirection("🔥 مرحبا") === "rtl");
check("digit-led arabic -> rtl", captionDirection("123 نعم") === "rtl");
check("punctuation-led hebrew -> rtl", captionDirection("«שלום»") === "rtl");
check("empty -> ltr (safe default)", captionDirection("") === "ltr");
check("emoji-only -> ltr (safe default)", captionDirection("🔥💯🚀") === "ltr");

// pagesDirection: decided by the first token that carries a strong letter, so a
// leading emoji-only token does not force ltr on an Arabic caption.
check(
  "pages: emoji token then arabic -> rtl",
  pagesDirection([{ tokens: [{ text: "🔥" }, { text: "مرحبا" }] }]) === "rtl",
);
check(
  "pages: latin caption -> ltr",
  pagesDirection([{ tokens: [{ text: "download" }, { text: "now" }] }]) === "ltr",
);

console.log(`\n${pass} passed, ${fails.length} failed`);
if (fails.length) {
  for (const f of fails) console.log("  FAILED: " + f);
  process.exit(1);
}
