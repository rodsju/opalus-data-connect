import React from "react";

export function Switch({ label, checked, disabled, onChange, style, ...rest }) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1, fontFamily: "var(--font-body)", fontSize: "var(--text-sm)", color: "var(--text-body)", ...style }} {...rest}>
      <input type="checkbox" role="switch" checked={!!checked} disabled={disabled} onChange={onChange}
        style={{ position: "absolute", opacity: 0, width: 0, height: 0 }} />
      <span style={{ width: 38, height: 22, flexShrink: 0, borderRadius: 999, padding: 2,
        background: checked ? "var(--teal-500)" : "var(--grey-300)", display: "inline-flex",
        transition: "background-color var(--duration-normal) var(--ease-standard)" }}>
        <span style={{ width: 18, height: 18, borderRadius: 999, background: "var(--grey-0)",
          boxShadow: "var(--shadow-xs)", transform: checked ? "translateX(16px)" : "translateX(0)",
          transition: "transform var(--duration-normal) var(--ease-standard)" }} />
      </span>
      {label}
    </label>
  );
}
