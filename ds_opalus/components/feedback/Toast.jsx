import React from "react";
import { Icon } from "../core/Icon.jsx";

const ICONS = { info: "info", success: "check-circle", warning: "alert-triangle", danger: "alert-octagon" };
const ACCENT = { info: "var(--blue-300)", success: "var(--teal-300)", warning: "var(--amber-500)", danger: "var(--red-500)" };

export function Toast({ title, children, tone = "info", onClose, action, style, ...rest }) {
  return (
    <div role="status" style={{ display: "flex", gap: 12, alignItems: "flex-start", minWidth: 300, maxWidth: 420,
      padding: "14px 16px", background: "var(--navy-800)", color: "var(--text-inverse)",
      borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-xl)", ...style }} {...rest}>
      <span style={{ color: ACCENT[tone], marginTop: 1 }}><Icon name={ICONS[tone]} size={18} /></span>
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && <div style={{ fontFamily: "var(--font-body)", fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)" }}>{title}</div>}
        {children && <div style={{ fontSize: "var(--text-xs)", color: "var(--text-inverse-muted)", marginTop: 3 }}>{children}</div>}
        {action && <div style={{ marginTop: 10 }}>{action}</div>}
      </div>
      {onClose && (
        <button type="button" aria-label="Fechar" onClick={onClose}
          style={{ border: 0, background: "transparent", color: "rgba(255,255,255,.6)", cursor: "pointer", padding: 0, height: 18 }}>
          <Icon name="x" size={16} />
        </button>
      )}
    </div>
  );
}
