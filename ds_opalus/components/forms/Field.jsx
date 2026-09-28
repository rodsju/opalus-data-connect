import React from "react";

export function Field({ label, hint, error, required, htmlFor, children, style, ...rest }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, ...style }} {...rest}>
      {label && (
        <label htmlFor={htmlFor} style={{ fontFamily: "var(--font-ui)", fontSize: "var(--text-2xs)", fontWeight: "var(--weight-semibold)",
          letterSpacing: "var(--tracking-wide)", textTransform: "uppercase", color: "var(--text-secondary)" }}>
          {label}{required && <span style={{ color: "var(--danger)", marginLeft: 3 }}>*</span>}
        </label>
      )}
      {children}
      {(error || hint) && (
        <span style={{ fontSize: "var(--text-xs)", color: error ? "var(--danger-text)" : "var(--text-tertiary)" }}>{error || hint}</span>
      )}
    </div>
  );
}
