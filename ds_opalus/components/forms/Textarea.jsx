import React from "react";

export function Textarea({ invalid, disabled, rows = 4, style, ...rest }) {
  const [f, setF] = React.useState(false);
  return (
    <textarea rows={rows} disabled={disabled} onFocus={() => setF(true)} onBlur={() => setF(false)}
      style={{ width: "100%", padding: "10px 12px", resize: "vertical", outline: "none",
        background: disabled ? "var(--grey-50)" : "var(--grey-0)", borderRadius: "var(--radius-md)",
        border: `1px solid ${invalid ? "var(--danger)" : f ? "var(--border-focus)" : "var(--border-default)"}`,
        boxShadow: f ? "var(--shadow-focus)" : "none", fontFamily: "var(--font-body)",
        fontSize: "var(--text-sm)", lineHeight: "var(--leading-normal)", color: "var(--text-primary)",
        transition: "var(--transition-colors)", ...style }} {...rest} />
  );
}
