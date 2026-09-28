import React from "react";

const PADS = { sm: 16, md: 24, lg: 32 };

export function Card({ children, padding = "md", interactive, tone = "default", header, footer, style, onClick, ...rest }) {
  const [h, setH] = React.useState(false);
  const p = PADS[padding] ?? PADS.md;
  const tones = {
    default: { background: "var(--surface-card)", border: "1px solid var(--border-default)", color: "var(--text-body)" },
    sunken: { background: "var(--surface-sunken)", border: "1px solid var(--border-muted)", color: "var(--text-body)" },
    brand: { background: "var(--gradient-navy)", border: "1px solid var(--navy-800)", color: "var(--text-inverse)" },
    accent: { background: "var(--navy-50)", border: "1px solid var(--navy-200)", color: "var(--text-body)" },
  }[tone];
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{ ...tones, borderRadius: "var(--radius-lg)", overflow: "hidden",
        boxShadow: interactive && h ? "var(--shadow-lg)" : "var(--shadow-sm)",
        transform: interactive && h ? "translateY(-2px)" : "none",
        cursor: interactive ? "pointer" : "default",
        transition: "box-shadow var(--duration-normal) var(--ease-standard),transform var(--duration-normal) var(--ease-standard)",
        ...style }}
      {...rest}
    >
      {header && <div style={{ padding: `${p}px ${p}px 0` }}>{header}</div>}
      <div style={{ padding: p }}>{children}</div>
      {footer && <div style={{ padding: `0 ${p}px ${p}px` }}>{footer}</div>}
    </div>
  );
}
