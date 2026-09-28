import React from "react";
import { Icon } from "./Icon.jsx";

export function Tag({ children, onRemove, selected, onClick, style, ...rest }) {
  const [h, setH] = React.useState(false);
  const interactive = !!onClick;
  return (
    <span
      onClick={onClick}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{ display: "inline-flex", alignItems: "center", gap: 7, height: 28, padding: onRemove ? "0 6px 0 12px" : "0 12px",
        fontFamily: "var(--font-body)", fontSize: "var(--text-xs)", fontWeight: "var(--weight-medium)",
        borderRadius: "var(--radius-full)", cursor: interactive ? "pointer" : "default",
        background: selected ? "var(--navy-700)" : h && interactive ? "var(--grey-100)" : "var(--grey-50)",
        color: selected ? "var(--grey-0)" : "var(--text-body)",
        border: selected ? "1px solid var(--navy-700)" : "1px solid var(--grey-200)",
        transition: "var(--transition-colors)", ...style }}
      {...rest}
    >
      {children}
      {onRemove && (
        <button type="button" aria-label="Remover" onClick={(e) => { e.stopPropagation(); onRemove(e); }}
          style={{ display: "inline-flex", border: 0, background: "transparent", padding: 2, borderRadius: 999,
            color: "inherit", cursor: "pointer", opacity: 0.6 }}>
          <Icon name="x" size={13} />
        </button>
      )}
    </span>
  );
}
