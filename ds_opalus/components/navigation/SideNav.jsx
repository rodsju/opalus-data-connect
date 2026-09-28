import React from "react";
import { Icon } from "../core/Icon.jsx";
import { Logo } from "../core/Logo.jsx";

export function SideNav({ items = [], value, onChange, footer, assetBase = "assets", width = 248, style, ...rest }) {
  return (
    <nav style={{ width, flexShrink: 0, background: "var(--navy-800)", color: "var(--text-inverse)",
      display: "flex", flexDirection: "column", ...style }} {...rest}>
      <div style={{ padding: "22px 20px 26px" }}><Logo tone="white" height={26} base={assetBase} /></div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2, padding: "0 12px", overflow: "auto" }}>
        {items.map((it) => {
          if (it.section) return <div key={it.section} style={{ fontFamily: "var(--font-ui)", fontSize: "var(--text-3xs)",
            fontWeight: 600, letterSpacing: "var(--tracking-widest)", textTransform: "uppercase",
            color: "rgba(255,255,255,.42)", padding: "18px 10px 7px" }}>{it.section}</div>;
          const on = it.id === value;
          return (
            <button key={it.id} type="button" onClick={() => onChange && onChange(it.id)}
              style={{ display: "flex", alignItems: "center", gap: 11, width: "100%", height: 40, padding: "0 10px",
                border: 0, borderRadius: "var(--radius-md)", cursor: "pointer", textAlign: "left",
                background: on ? "rgba(255,255,255,.12)" : "transparent",
                color: on ? "var(--grey-0)" : "rgba(255,255,255,.72)",
                fontFamily: "var(--font-body)", fontSize: "var(--text-sm)",
                fontWeight: on ? "var(--weight-semibold)" : "var(--weight-regular)",
                transition: "var(--transition-colors)" }}>
              <Icon name={it.icon} size={18} />
              <span style={{ flex: 1 }}>{it.label}</span>
              {it.count != null && <span style={{ fontFamily: "var(--font-ui)", fontSize: "var(--text-3xs)", fontWeight: 600,
                background: "var(--teal-500)", color: "var(--grey-0)", padding: "1px 7px", borderRadius: 999 }}>{it.count}</span>}
            </button>
          );
        })}
      </div>
      {footer && <div style={{ padding: 16, borderTop: "1px solid rgba(255,255,255,.1)" }}>{footer}</div>}
    </nav>
  );
}
