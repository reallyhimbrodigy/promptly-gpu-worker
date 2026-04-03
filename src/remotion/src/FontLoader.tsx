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
@font-face {
  font-family: 'Bebas Neue';
  src: url('file://${FONT_DIR}/BebasNeue-Regular.ttf') format('truetype');
  font-weight: 400;
  font-style: normal;
}
@font-face {
  font-family: 'Permanent Marker';
  src: url('file://${FONT_DIR}/PermanentMarker-Regular.ttf') format('truetype');
  font-weight: 400;
  font-style: normal;
}
@font-face {
  font-family: 'Poppins';
  src: url('file://${FONT_DIR}/Poppins-SemiBold.ttf') format('truetype');
  font-weight: 600;
  font-style: normal;
}
@font-face {
  font-family: 'Poppins';
  src: url('file://${FONT_DIR}/Poppins-Bold.ttf') format('truetype');
  font-weight: 700;
  font-style: normal;
}
@font-face {
  font-family: 'Poppins';
  src: url('file://${FONT_DIR}/Poppins-ExtraBold.ttf') format('truetype');
  font-weight: 800;
  font-style: normal;
}
@font-face {
  font-family: 'Bangers';
  src: url('file://${FONT_DIR}/Bangers-Regular.ttf') format('truetype');
  font-weight: 400;
  font-style: normal;
}
@font-face {
  font-family: 'Oswald';
  src: url('file://${FONT_DIR}/Oswald-Variable.ttf') format('truetype');
  font-weight: 200 700;
  font-style: normal;
}
@font-face {
  font-family: 'Playfair Display';
  src: url('file://${FONT_DIR}/PlayfairDisplay-Variable.ttf') format('truetype');
  font-weight: 400 900;
  font-style: normal;
}
@font-face {
  font-family: 'Space Grotesk';
  src: url('file://${FONT_DIR}/SpaceGrotesk-Variable.ttf') format('truetype');
  font-weight: 300 700;
  font-style: normal;
}
@font-face {
  font-family: 'Nunito';
  src: url('file://${FONT_DIR}/Nunito-Variable.ttf') format('truetype');
  font-weight: 200 900;
  font-style: normal;
}
@font-face {
  font-family: 'Inter';
  src: url('file://${FONT_DIR}/Inter-Variable.ttf') format('truetype');
  font-weight: 100 900;
  font-style: normal;
}
@font-face {
  font-family: 'Anton';
  src: url('file://${FONT_DIR}/Anton-Regular.ttf') format('truetype');
  font-weight: 400;
  font-style: normal;
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
