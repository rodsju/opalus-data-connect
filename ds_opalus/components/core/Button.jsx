import React from "react";
import { Icon } from "./Icon.jsx";

const SIZES = {
  sm: { height: 32, padding: "0 12px", fontSize: "var(--text-xs)", gap: 6, icon: 16 },
  md: { height: 40, padding: "0 18px", fontSize: "var(--text-sm)", gap: 8, icon: 18 },
  lg: { height: 48, padding: "0 26px", fontSize: "var(--text-md)", gap: 10, icon: 20 },
};

const VARIANTS = {
  primary: { background: "var(--navy-700)", color: "var(--grey-0)", border: "1px solid var(--navy-700)", hover: "var(--navy-800)", active: "var(--navy-900)" },
  secondary: { background: "var(--grey-0)", color: "var(--navy-700)", border: "1px solid var(--grey-300)", hover: "var(--grey-50)", active: "var(--grey-100)" },
  accent: { background: "var(--blue-600)", color: "var(--grey-0)", border: "1px solid var(--blue-600)", hover: "var(--blue-700)", active: "var(--navy-700)" },
  ghost: { background: "transparent", color: "var(--navy-700)", border: "1px solid transparent", hover: "var(--navy-50)", active: "var(--navy-100)" },
  danger: { background: "var(--red-500)", color: "var(--grey-0)", border: "1px solid var(--red-500)", hover: "var(--red-700)", active: "var(--red-700)" },
  inverse: { background: "var(--grey-0)", color: "var(--navy-700)", border: "1px solid var(--grey-0)", hover: "var(--navy-100)", active: "var(--navy-200)" },
};

export function Button({ children, variant = "primary", size = "md", icon, iconAfter, disabled, fullWidth, type = "button", onClick, style, ...rest }) {
  const [h, setH] = React.useState(false);
  const [a, setA] = React.useState(false);
  const s = SIZES[size] || SIZES.md;
  const v = VARIANTS[variant] || VARIANTS.primary;
  return (
    <button
      type={type}
      disabled={disabled}
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => { setH(false); setA(false); }}
      onMouseDown={() => setA(true)}
      onMouseUp={() => setA(false)}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center", gap: s.gap,
        height: s.height, padding: s.padding, width: fullWidth ? "100%" : undefined,
        fontFamily: "var(--font-body)", fontSize: s.fontSize, fontWeight: "var(--weight-semibold)",
        letterSpacing: "var(--tracking-tight)", borderRadius: "var(--radius-md)", cursor: disabled ? "not-allowed" : "pointer",
        background: a ? v.active : h ? v.hover : v.background, color: v.color, border: v.border,
        boxShadow: variant === "primary" || variant === "accent" || variant === "danger" ? "var(--shadow-xs)" : "none",
        opacity: disabled ? 0.45 : 1, transition: "var(--transition-colors)", whiteSpace: "nowrap", ...style,
      }}
      {...rest}
    >
      {icon && <Icon name={icon} size={s.icon} />}
      {children}
      {iconAfter && <Icon name={iconAfter} size={s.icon} />}
    </button>
  );
}
