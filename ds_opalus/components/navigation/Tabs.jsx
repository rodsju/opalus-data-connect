import React from "react";
import { Icon } from "../core/Icon.jsx";

export function Tabs({ items = [], value, onChange, variant = "underline", style, ...rest }) {
  const active = value ?? (items[0] && (items[0].id || items[0]));
  const norm = items.map((i) => (typeof i === "string" ? { id: i, label: i } : i));
  if (variant === "pill") {
    return (
      <div style={{ display: "inline-flex", gap: 4, padding: 4, background: "var(--grey-100)", borderRadius: "var(--radius-md)", ...style }} {...rest}>
        {norm.map((t) => {
          const on = t.id === active;
          return (
            <button key={t.id} type="button" onClick={() => onChange && onChange(t.id)}
              style={{ display: "inline-flex", alignItems: "center", gap: 7, height: 32, padding: "0 14px", border: 0,
                borderRadius: "var(--radius-sm)", cursor: "pointer", fontFamily: "var(--font-body)",
                fontSize: "var(--text-xs)", fontWeight: "var(--weight-semibold)",
                background: on ? "var(--grey-0)" : "transparent", color: on ? "var(--navy-700)" : "var(--text-secondary)",
                boxShadow: on ? "var(--shadow-xs)" : "none", transition: "var(--transition-colors)" }}>
              {t.icon && <Icon name={t.icon} size={15} />}{t.label}
            </button>
          );
        })}
      </div>
    );
  }
  return (
    <div style={{ display: "flex", gap: 28, borderBottom: "1px solid var(--border-default)", ...style }} {...rest}>
      {norm.map((t) => {
        const on = t.id === active;
        return (
          <button key={t.id} type="button" onClick={() => onChange && onChange(t.id)}
            style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: "0 0 12px", border: 0,
              background: "transparent", cursor: "pointer", fontFamily: "var(--font-body)",
              fontSize: "var(--text-sm)", fontWeight: on ? "var(--weight-semibold)" : "var(--weight-medium)",
              color: on ? "var(--navy-700)" : "var(--text-secondary)",
              boxShadow: on ? "inset 0 -2px 0 var(--navy-700)" : "none", transition: "var(--transition-colors)" }}>
            {t.icon && <Icon name={t.icon} size={16} />}{t.label}
            {t.count != null && (
              <span style={{ fontFamily: "var(--font-ui)", fontSize: "var(--text-3xs)", fontWeight: 600,
                background: on ? "var(--navy-100)" : "var(--grey-100)", color: on ? "var(--navy-700)" : "var(--text-secondary)",
                padding: "1px 7px", borderRadius: 999 }}>{t.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
