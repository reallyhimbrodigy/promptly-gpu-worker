// Shim that replaces @remotion/google-fonts/* at bundle time via webpack
// resolve.alias (see prebundle.mjs). The real package injects @font-face rules
// pointing at fonts.gstatic.com on every loadFont() call, which forces
// Chromium to download fonts over the network during render. We ship the .ttf
// files inside the Modal image (/usr/share/fonts/truetype, registered by
// fc-cache at image build time), so fontconfig resolves every font-family by
// name from local disk. This shim is a no-op that returns the same object
// shape the components destructure (`.fontFamily`), keeping components
// byte-identical while eliminating all network fetches at render time.
//
// Zero runtime cost. Zero network dependency. Zero @font-face rules.
// Chromium finds Playfair Display, Montserrat, etc. via fontconfig and
// renders from local .ttf.

export interface GoogleFontShimResult {
  fontFamily: string;
  fonts: Record<string, never>;
  unicodeRanges: Record<string, never>;
  waitUntilDone: () => Promise<void>;
}

export const makeShim = (fontFamily: string) => ({
  loadFont: (_style?: string, _options?: unknown): GoogleFontShimResult => ({
    fontFamily,
    fonts: {},
    unicodeRanges: {},
    waitUntilDone: () => Promise.resolve(),
  }),
  fontFamily,
});
