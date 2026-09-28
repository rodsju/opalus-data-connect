import React from "react";
import { Icon } from "../core/Icon.jsx";

const SIZES = { sm: 34, md: 42, lg: 50 };

export function Select({ options = [], placeholder, invalid, disabled, size = "md", style, ...rest }) {
  const [f, setF] = React.useState(false);
  const h = SIZES[size] || SIZES.md;
  return (
    <div style={{ position: "relative", display: "flex", alignItems: "center", height: h,
      background: disabled ? "var(--grey-50)" : "var(--grey-0)", borderRadius: "var(--radius-md)",
      border: `1px solid ${invalid ? "var(--danger)" : f ? "var(--border-focus)" : "var(--border-default)"}`,
      boxShadow: f ? "var(--shadow-focus)" : "none", transition: "var(--transition-colors)", ...style }}>
      <select disabled={disabled} onFocus={() => setF(true)} onBlur={() => setF(false)}
        style={{ appearance: "none", width: "100%", height: "100%", border: 0, outline: "none",
          background: "transparent", padding: "0 34px 0 12px", fontFamily: "var(--font-body)",
          fontSize: size === "sm" ? "var(--text-xs)" : "var(--text-sm)", color: "var(--text-primary)", cursor: "pointer" }}
        {...rest}>
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((o) => {
          const v = typeof o === "string" ? o : o.value;
          const l = typeof o === "string" ? o : o.label;
          return <option key={v} value={v}>{l}</option>;
        })}
      </select>
      <span style={{ position: "absolute", right: 11, pointerEvents: "none", color: "var(--text-tertiary)" }}>
        <Icon name="chevron-down" size={16} />
      </span>
    </div>
  );
}
