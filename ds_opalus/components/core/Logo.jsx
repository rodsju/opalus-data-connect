import React from "react";

const FILES = {
  color: { horizontal: "logo-horizontal.png", vertical: "logo-vertical.png", symbol: "symbol.png" },
  white: { horizontal: "logo-horizontal-white.png", vertical: "logo-vertical-white.png", symbol: "symbol-white.png" },
  mono: { horizontal: "logo-horizontal-mono.png", vertical: "logo-vertical-mono.png", symbol: "symbol-mono.png" },
};

export function Logo({ lockup = "horizontal", tone = "color", height = 32, base = "assets", style, ...rest }) {
  const file = (FILES[tone] || FILES.color)[lockup] || FILES.color.horizontal;
  return (
    <img src={`${base}/${file}`} alt="Opalus"
      style={{ height, width: "auto", display: "block", ...style }} {...rest} />
  );
}
