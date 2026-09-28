import React from "react";
import { Icon } from "../core/Icon.jsx";
import { Logo } from "../core/Logo.jsx";

export function TopBar({ links = [], active, onNavigate, action, tone = "light", assetBase = "assets", style, ...rest }) {
  const dark = tone === "dark";
  return (
    <header style={{ display: "flex", alignItems: "center", gap: 32, height: 72, padding: "0 32px",
      background: dark ? "var(--navy-700)" : "var(--glass)", backdropFilter: dark ? undefined : "var(--glass-blur)",
      borderBottom: dark ? "1px solid var(--navy-800)" : "1px solid var(--border-default)", ...style }} {...rest}>
      <Logo tone={dark ? "white" : "color"} height={28} base={assetBase} />
      <nav style={{ display: "flex", gap: 26, flex: 1 }}>
        {links.map((l) => {
          const label = typeof l === "string" ? l : l.label;
          const on = label === active;
          return (
            <a key={label} href={(typeof l === "object" && l.href) || "#"}
              onClick={(e) => { if (onNavigate) { e.preventDefault(); onNavigate(label); } }}
              style={{ fontFamily: "var(--font-body)", fontSize: "var(--text-sm)",
                fontWeight: on ? "var(--weight-semibold)" : "var(--weight-medium)", textDecoration: "none",
                color: dark ? (on ? "var(--grey-0)" : "rgba(255,255,255,.75)") : (on ? "var(--navy-700)" : "var(--text-secondary)") }}>
              {label}
            </a>
          );
        })}
      </nav>
      {action}
    </header>
  );
}
