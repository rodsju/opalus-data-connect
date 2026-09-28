import React from "react";
import { Icon } from "../core/Icon.jsx";

export function DataTable({ columns = [], rows = [], dense, onRowClick, style, ...rest }) {
  const [hover, setHover] = React.useState(-1);
  const pad = dense ? "8px 14px" : "13px 16px";
  return (
    <div style={{ background: "var(--surface-card)", border: "1px solid var(--border-default)",
      borderRadius: "var(--radius-lg)", overflow: "hidden", ...style }} {...rest}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ background: "var(--surface-sunken)" }}>
            {columns.map((c) => (
              <th key={c.key} style={{ textAlign: c.align || "left", padding: pad, fontFamily: "var(--font-ui)",
                fontSize: "var(--text-3xs)", fontWeight: 600, letterSpacing: "var(--tracking-widest)",
                textTransform: "uppercase", color: "var(--text-secondary)", whiteSpace: "nowrap",
                borderBottom: "1px solid var(--border-default)", width: c.width }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                  {c.label}{c.sorted && <Icon name={c.sorted === "desc" ? "arrow-down" : "arrow-up"} size={12} />}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? i} onClick={() => onRowClick && onRowClick(r)}
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(-1)}
              style={{ background: hover === i ? "var(--surface-hover)" : "transparent",
                cursor: onRowClick ? "pointer" : "default", transition: "background-color var(--duration-fast) var(--ease-standard)" }}>
              {columns.map((c) => (
                <td key={c.key} style={{ textAlign: c.align || "left", padding: pad, fontFamily: "var(--font-body)",
                  fontSize: dense ? "var(--text-xs)" : "var(--text-sm)", color: "var(--text-body)",
                  borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--border-muted)",
                  fontVariantNumeric: c.numeric ? "tabular-nums" : undefined,
                  fontFamily: c.numeric ? "var(--font-ui)" : "var(--font-body)" }}>
                  {r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
