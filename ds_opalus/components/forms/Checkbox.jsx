import React from "react";
import { Icon } from "../core/Icon.jsx";

export function Checkbox({ label, checked, indeterminate, disabled, onChange, style, ...rest }) {
  const on = checked || indeterminate;
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: 10, cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1, fontFamily: "var(--font-body)", fontSize: "var(--text-sm)", color: "var(--text-body)", ...style }} {...rest}>
      <input type="checkbox" checked={!!checked} disabled={disabled} onChange={onChange}
        style={{ position: "absolute", opacity: 0, width: 0, height: 0 }} />
      <span style={{ width: 18, height: 18, flexShrink: 0, display: "inline-flex", alignItems: "center", justifyContent: "center",
        borderRadius: "var(--radius-xs)", background: on ? "var(--navy-700)" : "var(--grey-0)",
        border: on ? "1px solid var(--navy-700)" : "1px solid var(--grey-300)", color: "var(--grey-0)",
        transition: "var(--transition-colors)" }}>
        {indeterminate ? <Icon name="minus" size={13} strokeWidth={3} /> : checked ? <Icon name="check" size={13} strokeWidth={3} /> : null}
      </span>
      {label}
    </label>
  );
}
