import React from "react";
import { Icon } from "../core/Icon.jsx";

export function Breadcrumbs({ items = [], style, ...rest }) {
  return (
    <nav style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "var(--font-body)", fontSize: "var(--text-xs)", ...style }} {...rest}>
      {items.map((it, i) => {
        const last = i === items.length - 1;
        const label = typeof it === "string" ? it : it.label;
        const href = typeof it === "string" ? undefined : it.href;
        return (
          <React.Fragment key={label}>
            {last ? <span style={{ color: "var(--text-primary)", fontWeight: "var(--weight-semibold)" }}>{label}</span>
                  : <a href={href || "#"} style={{ color: "var(--text-secondary)" }}>{label}</a>}
            {!last && <span style={{ color: "var(--grey-300)", display: "inline-flex" }}><Icon name="chevron-right" size={13} /></span>}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
