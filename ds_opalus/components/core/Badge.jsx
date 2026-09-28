import React from "react";
import { Icon } from "./Icon.jsx";

const TONES = {
  neutral: ["var(--grey-100)", "var(--grey-700)"],
  brand: ["var(--navy-100)", "var(--navy-700)"],
  info: ["var(--blue-100)", "var(--blue-700)"],
  success: ["var(--teal-100)", "var(--teal-700)"],
  warning: ["var(--amber-100)", "var(--amber-700)"],
  danger: ["var(--red-100)", "var(--red-700)"],
  purple: ["var(--purple-100)", "var(--purple-700)"],
};

export function Badge({ children, tone = "neutral", icon, dot, size = "md", style, ...rest }) {
  const [bg, fg] = TONES[tone] || TONES.neutral;
  const sm = size === "sm";
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, background: bg, color: fg,
      fontFamily: "var(--font-ui)", fontSize: sm ? "var(--text-3xs)" : "var(--text-2xs)", fontWeight: "var(--weight-semibold)",
      letterSpacing: "var(--tracking-wide)", textTransform: "uppercase", padding: sm ? "2px 8px" : "4px 10px",
      borderRadius: "var(--radius-full)", whiteSpace: "nowrap", ...style }} {...rest}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: 999, background: fg }} />}
      {icon && <Icon name={icon} size={sm ? 11 : 13} />}
      {children}
    </span>
  );
}
