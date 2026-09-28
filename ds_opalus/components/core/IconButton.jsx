import React from "react";
import { Icon } from "./Icon.jsx";

const SIZES = { sm: 30, md: 38, lg: 46 };
const GLYPH = { sm: 16, md: 18, lg: 22 };

export function IconButton({ icon, label, variant = "ghost", size = "md", disabled, active, onClick, style, ...rest }) {
  const [h, setH] = React.useState(false);
  const box = SIZES[size] || SIZES.md;
  const tone = {
    ghost: { bg: active ? "var(--navy-100)" : h ? "var(--navy-50)" : "transparent", fg: "var(--navy-700)", bd: "1px solid transparent" },
    outline: { bg: h ? "var(--grey-50)" : "var(--grey-0)", fg: "var(--navy-700)", bd: "1px solid var(--grey-300)" },
    solid: { bg: h ? "var(--navy-800)" : "var(--navy-700)", fg: "var(--grey-0)", bd: "1px solid var(--navy-700)" },
    inverse: { bg: h ? "rgba(255,255,255,.18)" : "rgba(255,255,255,.08)", fg: "var(--grey-0)", bd: "1px solid rgba(255,255,255,.16)" },
  }[variant];
  return (
    <button
      type="button" aria-label={label} disabled={disabled} onClick={onClick}
      onMouseEnter={() => setH(true)} onMouseLeave={() => setH(false)}
      style={{ width: box, height: box, display: "inline-flex", alignItems: "center", justifyContent: "center",
        borderRadius: "var(--radius-md)", background: tone.bg, color: tone.fg, border: tone.bd,
        cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.45 : 1,
        transition: "var(--transition-colors)", ...style }}
      {...rest}
    >
      <Icon name={icon} size={GLYPH[size] || 18} />
    </button>
  );
}
