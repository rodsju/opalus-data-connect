import React from "react";

const SEQ = ["var(--chart-1)","var(--chart-2)","var(--chart-3)","var(--chart-4)","var(--chart-5)","var(--chart-6)","var(--chart-7)","var(--chart-8)"];

export function BarChart({ data = [], height = 180, color, showValues, style, ...rest }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, ...style }} {...rest}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height,
        borderBottom: "1px solid var(--chart-grid)", paddingBottom: 1 }}>
        {data.map((d, i) => (
          <div key={d.label} style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "flex-end", alignItems: "center", gap: 6, height: "100%" }}>
            {showValues && <span style={{ fontFamily: "var(--font-ui)", fontSize: "var(--text-3xs)", fontWeight: 600,
              fontVariantNumeric: "tabular-nums", color: "var(--text-secondary)" }}>{d.value}</span>}
            <div style={{ width: "100%", height: `${(d.value / max) * 100}%`,
              background: d.color || color || SEQ[i % SEQ.length],
              borderRadius: "var(--radius-sm) var(--radius-sm) 0 0",
              transition: "height var(--duration-slow) var(--ease-standard)" }} />
          </div>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        {data.map((d) => (
          <span key={d.label} style={{ flex: 1, textAlign: "center", fontFamily: "var(--font-ui)",
            fontSize: "var(--text-3xs)", color: "var(--text-tertiary)", letterSpacing: "var(--tracking-wide)",
            textTransform: "uppercase" }}>{d.label}</span>
        ))}
      </div>
    </div>
  );
}
