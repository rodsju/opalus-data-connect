import React from "react";
import { Icon } from "../core/Icon.jsx";

const SIZES = { sm: 34, md: 42, lg: 50 };

export function Input({ icon, iconAfter, invalid, disabled, size = "md", style, ...rest }) {
  const [f, setF] = React.useState(false);
  const h = SIZES[size] || SIZES.md;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, height: h, padding: "0 12px",
      background: disabled ? "var(--grey-50)" : "var(--grey-0)", borderRadius: "var(--radius-md)",
      border: `1px solid ${invalid ? "var(--danger)" : f ? "var(--border-focus)" : "var(--border-default)"}`,
      boxShadow: f ? (invalid ? "var(--shadow-focus-danger)" : "var(--shadow-focus)") : "none",
      transition: "var(--transition-colors)", ...style }}>
      {icon && <Icon name={icon} size={16} color="var(--text-tertiary)" />}
      <input disabled={disabled} onFocus={() => setF(true)} onBlur={() => setF(false)}
        style={{ flex: 1, minWidth: 0, border: 0, outline: "none", background: "transparent",
          fontFamily: "var(--font-body)", fontSize: size === "sm" ? "var(--text-xs)" : "var(--text-sm)",
          color: "var(--text-primary)" }} {...rest} />
      {iconAfter && <Icon name={iconAfter} size={16} color="var(--text-tertiary)" />}
    </div>
  );
}
