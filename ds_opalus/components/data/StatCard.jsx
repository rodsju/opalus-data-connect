import React from "react";
import { Icon } from "../core/Icon.jsx";

export function StatCard({ label, value, unit, delta, deltaTone, icon, footnote, tone = "default", style, ...rest }) {
  const dark = tone === "brand";
  const up = typeof delta === "string" && delta.trim().startsWith("+");
  const dt = deltaTone || (up ? "success" : "danger");
  const dc = { success: "var(--teal-500)", danger: "var(--red-500)", neutral: "var(--text-secondary)" }[dt];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: 20,
      background: dark ? "var(--gradient-navy)" : "var(--surface-card)",
      border: dark ? "1px solid var(--navy-800)" : "1px solid var(--border-default)",
      borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow-sm)", ...style }} {...rest}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        {icon && <span style={{ color: dark ? "var(--navy-300)" : "var(--navy-400)" }}><Icon name={icon} size={16} /></span>}
        <span style={{ fontFamily: "var(--font-ui)", fontSize: "var(--text-2xs)", fontWeight: 600,
          letterSpacing: "var(--tracking-wide)", textTransform: "uppercase",
          color: dark ? "var(--text-inverse-muted)" : "var(--text-secondary)" }}>{label}</span>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontFamily: "var(--font-ui)", fontSize: "var(--text-4xl)", fontWeight: 600,
          fontVariantNumeric: "tabular-nums", letterSpacing: "var(--tracking-tight)", lineHeight: 1,
          color: dark ? "var(--grey-0)" : "var(--navy-700)" }}>{value}</span>
        {unit && <span style={{ fontSize: "var(--text-sm)", color: dark ? "var(--text-inverse-muted)" : "var(--text-tertiary)" }}>{unit}</span>}
        {delta && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 3, marginLeft: 2,
            fontFamily: "var(--font-ui)", fontSize: "var(--text-xs)", fontWeight: 600, color: dc }}>
            <Icon name={up ? "trending-up" : "trending-down"} size={14} />{delta}
          </span>
        )}
      </div>
      {footnote && <span style={{ fontSize: "var(--text-2xs)", color: dark ? "rgba(255,255,255,.55)" : "var(--text-tertiary)" }}>{footnote}</span>}
    </div>
  );
}
