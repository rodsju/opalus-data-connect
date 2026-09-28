import React from "react";
import { Icon } from "../core/Icon.jsx";

export function Dialog({ open, title, description, children, footer, onClose, width = 520, style, ...rest }) {
  if (!open) return null;
  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 60, display: "flex", alignItems: "center",
      justifyContent: "center", padding: 24, background: "var(--surface-overlay)",
      backdropFilter: "blur(3px)" }} onClick={onClose}>
      <div role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}
        style={{ width: "100%", maxWidth: width, background: "var(--surface-card)", borderRadius: "var(--radius-xl)",
          boxShadow: "var(--shadow-xl)", overflow: "hidden", ...style }} {...rest}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 16, padding: "24px 24px 0" }}>
          <div style={{ flex: 1 }}>
            <h3 style={{ fontFamily: "var(--font-display)", fontSize: "var(--text-xl)", fontWeight: "var(--weight-bold)",
              color: "var(--text-primary)", margin: 0, letterSpacing: "var(--tracking-tight)" }}>{title}</h3>
            {description && <p style={{ margin: "6px 0 0", fontSize: "var(--text-sm)", color: "var(--text-secondary)" }}>{description}</p>}
          </div>
          {onClose && (
            <button type="button" aria-label="Fechar" onClick={onClose}
              style={{ border: 0, background: "transparent", color: "var(--text-tertiary)", cursor: "pointer", padding: 2 }}>
              <Icon name="x" size={20} />
            </button>
          )}
        </div>
        {children && <div style={{ padding: "20px 24px 0", fontSize: "var(--text-sm)", color: "var(--text-body)" }}>{children}</div>}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, padding: 24 }}>{footer}</div>
      </div>
    </div>
  );
}
