import React from "react";

export function Tooltip({ label, children, placement = "top", style, ...rest }) {
  const [open, setOpen] = React.useState(false);
  const pos = {
    top: { bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)" },
    bottom: { top: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)" },
    left: { right: "calc(100% + 8px)", top: "50%", transform: "translateY(-50%)" },
    right: { left: "calc(100% + 8px)", top: "50%", transform: "translateY(-50%)" },
  }[placement];
  return (
    <span style={{ position: "relative", display: "inline-flex", ...style }}
      onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} {...rest}>
      {children}
      <span role="tooltip" style={{ position: "absolute", ...pos, zIndex: 30, pointerEvents: "none",
        background: "var(--navy-800)", color: "var(--grey-0)", padding: "6px 10px",
        borderRadius: "var(--radius-sm)", fontFamily: "var(--font-body)", fontSize: "var(--text-2xs)",
        whiteSpace: "nowrap", boxShadow: "var(--shadow-md)", opacity: open ? 1 : 0,
        transition: "opacity var(--duration-fast) var(--ease-standard)" }}>{label}</span>
    </span>
  );
}
