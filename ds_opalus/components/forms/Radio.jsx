import React from "react";

export function Radio({ label, checked, disabled, name, value, onChange, style, ...rest }) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1, fontFamily: "var(--font-body)", fontSize: "var(--text-sm)", color: "var(--text-body)", ...style }} {...rest}>
      <input type="radio" name={name} value={value} checked={!!checked} disabled={disabled} onChange={onChange}
        style={{ position: "absolute", opacity: 0, width: 0, height: 0 }} />
      <span style={{ width: 18, height: 18, flexShrink: 0, borderRadius: 999, display: "inline-flex",
        alignItems: "center", justifyContent: "center", background: "var(--grey-0)",
        border: checked ? "5px solid var(--navy-700)" : "1px solid var(--grey-300)",
        transition: "var(--transition-colors)" }} />
      {label}
    </label>
  );
}
