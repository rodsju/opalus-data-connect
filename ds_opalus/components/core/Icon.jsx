import React from "react";

/* Lucide (lucide.dev) is the Opalus icon set — 1.75px stroke, rounded caps, which matches
   the symbol's soft geometry. The brand supplied no icon library of its own.
   Host pages must load: https://unpkg.com/lucide@0.544.0/dist/umd/lucide.js */
export function Icon({ name, size = 20, strokeWidth = 1.75, color = "currentColor", style, ...rest }) {
  const lib = typeof window !== "undefined" && window.lucide && window.lucide.icons;
  const toPascal = (s) => s.replace(/(^|-)([a-z])/g, (_, __, c) => c.toUpperCase());
  const node = lib && (lib[name] || lib[toPascal(name)]);
  const base = { width: size, height: size, flexShrink: 0, display: "block", ...style };
  if (!node) return React.createElement("span", { style: { ...base, borderRadius: 3, background: "var(--grey-200)" }, ...rest });
  const [, attrs, children] = node;
  return React.createElement(
    "svg",
    { ...attrs, width: size, height: size, stroke: color, strokeWidth, style: base, ...rest },
    (children || []).map((c, i) => React.createElement(c[0], { key: i, ...c[1] }))
  );
}
