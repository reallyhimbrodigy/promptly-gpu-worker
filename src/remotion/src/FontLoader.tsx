import React from "react";
import { continueRender, delayRender } from "remotion";

/**
 * Loads Montserrat fonts from the local font directory.
 * Fonts are loaded via CSS @font-face so Chromium can render them.
 */

const FONT_DIR = "/assets/fonts";

const FONT_FACES = `
@font-face {
  font-family: 'Montserrat';
  src: url('file://${FONT_DIR}/Montserrat-Bold.ttf') format('truetype');
  font-weight: 700;
  font-style: normal;
}
@font-face {
  font-family: 'Montserrat';
  src: url('file://${FONT_DIR}/Montserrat-ExtraBold.ttf') format('truetype');
  font-weight: 800;
  font-style: normal;
}
@font-face {
  font-family: 'Montserrat';
  src: url('file://${FONT_DIR}/Montserrat-Black.ttf') format('truetype');
  font-weight: 900;
  font-style: normal;
}
@font-face {
  font-family: 'Montserrat';
  src: url('file://${FONT_DIR}/Montserrat-BoldItalic.ttf') format('truetype');
  font-weight: 700;
  font-style: italic;
}
@font-face {
  font-family: 'Montserrat';
  src: url('file://${FONT_DIR}/Montserrat-ExtraBoldItalic.ttf') format('truetype');
  font-weight: 800;
  font-style: italic;
}
`;

export const FontLoader: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [handle] = React.useState(() => delayRender("Loading fonts"));

  React.useEffect(() => {
    // Inject @font-face CSS
    const style = document.createElement("style");
    style.textContent = FONT_FACES;
    document.head.appendChild(style);

    // Wait for fonts to load
    document.fonts.ready.then(() => {
      continueRender(handle);
    });

    return () => {
      document.head.removeChild(style);
    };
  }, [handle]);

  return <>{children}</>;
};
