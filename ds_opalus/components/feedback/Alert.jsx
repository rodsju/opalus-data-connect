import React from "react";
import { Icon } from "../core/Icon.jsx";

const TONES = {
  info: ["var(--blue-50)", "var(--blue-200)", "var(--blue-700)", "info"],
  success: ["var(--teal-50)", "var(--teal-100)", "var(--teal-700)", "check-circle"],
  warning: ["var(--amber-100)", "#f0dcb0", "var(--amber-700)", "alert-triangle"],
  danger: ["var(--red-100)", "#f2c4c1", "var(--red-700)", "alert-octagon"],
};

export function Alert({ title, children, tone = "info", icon, onClose, style, ...rest }) {
  const [bg, bd, fg, defIcon] = TONES[tone] || TONES.info;
  return (
    <div role="status" style={{ display: "flex", gap: 12, padding: "14px 16px", background: bg,
      border: `1px solid ${bd}`, borderRadius: "var(--radius-md)", color: fg, ...style }} {...rest}>
      <span style={{ marginTop: 1 }}><Icon name={icon || defIcon} size={18} /></span>
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && <div style={{ fontFamily: "var(--font-body)", fontSize: "var(--text-sm)", fontWeight: "var(--weight-semibold)", marginBottom: children ? 3 : 0 }}>{title}</div>}
        {children && <div style={{ fontSize: "var(--text-xs)", lineHeight: "var(--leading-normal)", opacity: 0.92 }}>{children}</div>}
      </div>
      {onClose && (
        <button type="button" aria-label="Fechar" onClick={onClose}
          style={{ border: 0, background: "transparent", color: "inherit", cursor: "pointer", opacity: 0.6, padding: 0, height: 18 }}>
          <Icon name="x" size={16} />
        </button>
      )}
    </div>
  );
}
