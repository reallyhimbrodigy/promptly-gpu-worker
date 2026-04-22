import React from "react";
import type { NotificationApp } from "./types";

interface IconProps {
  size: number;
}

interface TileProps {
  size: number;
  background: string;
  children: React.ReactNode;
  color?: string;
}

const Tile: React.FC<TileProps> = ({
  size,
  background,
  children,
  color = "#FFFFFF",
}) => (
  <div
    style={{
      width: size,
      height: size,
      background,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      color,
      lineHeight: 0,
    }}
  >
    {children}
  </div>
);

const ApplePayIcon: React.FC<IconProps> = ({ size }) => {
  const s = size * 0.58;
  return (
    <Tile size={size} background="#000000">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11" />
      </svg>
    </Tile>
  );
};

const VenmoIcon: React.FC<IconProps> = ({ size }) => {
  const s = size * 0.5;
  return (
    <Tile size={size} background="#3D95CE">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M19.27 2c.94 1.55 1.37 3.15 1.37 5.17 0 6.44-5.5 14.81-9.96 20.69H3.44L.56 3.39l6.81-.64 1.69 13.57C11.13 12.68 13.5 7.33 13.5 4.18c0-1.94-.33-3.26-.86-4.3L19.27 2z" />
      </svg>
    </Tile>
  );
};

const StripeIcon: React.FC<IconProps> = ({ size }) => {
  const s = size * 0.46;
  return (
    <Tile size={size} background="linear-gradient(135deg, #7A73FF 0%, #553ACF 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M13.976 9.15c-2.172-.806-3.356-1.426-3.356-2.409 0-.831.683-1.305 1.901-1.305 2.227 0 4.515.858 6.09 1.631l.89-5.494C18.252.975 15.697 0 12.165 0 9.667 0 7.589.654 6.104 1.872 4.56 3.147 3.757 4.992 3.757 7.218c0 4.039 2.467 5.76 6.476 7.219 2.585.92 3.445 1.574 3.445 2.583 0 .98-.84 1.545-2.354 1.545-1.875 0-4.965-.921-7.076-2.19l-.89 5.592C5.456 23.2 8.865 24 12.045 24c2.58 0 4.71-.636 6.29-1.866C19.953 20.726 21 18.57 21 16.014c0-4.163-2.538-5.88-7.024-6.864z" />
      </svg>
    </Tile>
  );
};

const IMessageIcon: React.FC<IconProps> = ({ size }) => {
  const s = size * 0.56;
  return (
    <Tile size={size} background="linear-gradient(180deg, #5BE368 0%, #30C040 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M12 2C6.477 2 2 5.813 2 10.5c0 2.61 1.39 4.96 3.57 6.53L4.5 21.5l5.03-2.52c.8.16 1.62.27 2.47.27 5.523 0 10-3.813 10-8.75S17.523 2 12 2zm-3 11.5a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm3 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3zm3 0a1.5 1.5 0 110-3 1.5 1.5 0 010 3z" />
      </svg>
    </Tile>
  );
};

const InstagramIcon: React.FC<IconProps> = ({ size }) => {
  const s = size * 0.54;
  return (
    <Tile size={size} background="linear-gradient(45deg, #FEDA77 0%, #F58529 25%, #DD2A7B 55%, #8134AF 85%, #515BD4 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
      </svg>
    </Tile>
  );
};

const EmailIcon: React.FC<IconProps> = ({ size }) => {
  const s = size * 0.48;
  return (
    <Tile size={size} background="linear-gradient(180deg, #30B8FF 0%, #0A84FF 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
      </svg>
    </Tile>
  );
};

const BankIcon: React.FC<IconProps> = ({ size }) => {
  const s = size * 0.52;
  return (
    <Tile size={size} background="linear-gradient(180deg, #4A5560 0%, #1E242C 100%)">
      <svg width={s} height={s} viewBox="0 0 24 24" fill="#FFFFFF">
        <path d="M12 1L1 7v2h22V7L12 1zM3 11v7h3v-7H3zm5 0v7h3v-7H8zm5 0v7h3v-7h-3zm5 0v7h3v-7h-3zM1 20v2h22v-2H1z" />
      </svg>
    </Tile>
  );
};

export const APP_ICONS: Record<NotificationApp, React.FC<IconProps>> = {
  "apple-pay": ApplePayIcon,
  venmo: VenmoIcon,
  stripe: StripeIcon,
  imessage: IMessageIcon,
  instagram: InstagramIcon,
  email: EmailIcon,
  bank: BankIcon,
};
