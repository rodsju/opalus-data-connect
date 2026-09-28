import React from "react";

export function ProgressBar({ value = 0, max = 100, label, showValue, tone = "brand", size = "md", style, ...rest }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  const fill = { brand: "var(--navy-700)", accent: "var(--blue-600)", success: "var(--teal-500)",
    warning: "var(--amber-500)", danger: "var(--red-500)" }[tone];
  const h = size === "sm" ? 5 : size === "lg" ? 12 : 8;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 7, ...style }} {...rest}>
      {(label || showValue) && (
        <div style={{ display: "flex", justifyContent: "space-between", fontFamily: "var(--font-ui)", fontSize: "var(--text-2xs)" }}>
          <span style={{ fontWeight: 600, letterSpacing: "var(--tracking-wide)", textTransform: "uppercase", color: "var(--text-secondary)" }}>{label}</span>
          {showValue && <span style={{ fontVariantNumeric: "tabular-nums", color: "var(--text-primary)", fontWeight: 600 }}>{Math.round(pct)}%</span>}
        </div>
      )}
      <div style={{ height: h, borderRadius: 999, background: "var(--grey-100)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 999, background: fill,
          transition: "width var(--duration-slow) var(--ease-standard)" }} />
      </div>
    </div>
  );
}
