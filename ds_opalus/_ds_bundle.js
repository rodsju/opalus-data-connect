/* @ds-bundle: {"format":4,"namespace":"OpalusDesignSystem_2ac06f","components":[{"name":"Badge","sourcePath":"components/core/Badge.jsx"},{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"Logo","sourcePath":"components/core/Logo.jsx"},{"name":"Tag","sourcePath":"components/core/Tag.jsx"},{"name":"BarChart","sourcePath":"components/data/BarChart.jsx"},{"name":"DataTable","sourcePath":"components/data/DataTable.jsx"},{"name":"ProgressBar","sourcePath":"components/data/ProgressBar.jsx"},{"name":"StatCard","sourcePath":"components/data/StatCard.jsx"},{"name":"Alert","sourcePath":"components/feedback/Alert.jsx"},{"name":"Dialog","sourcePath":"components/feedback/Dialog.jsx"},{"name":"Toast","sourcePath":"components/feedback/Toast.jsx"},{"name":"Tooltip","sourcePath":"components/feedback/Tooltip.jsx"},{"name":"Checkbox","sourcePath":"components/forms/Checkbox.jsx"},{"name":"Field","sourcePath":"components/forms/Field.jsx"},{"name":"Input","sourcePath":"components/forms/Input.jsx"},{"name":"Radio","sourcePath":"components/forms/Radio.jsx"},{"name":"Select","sourcePath":"components/forms/Select.jsx"},{"name":"Switch","sourcePath":"components/forms/Switch.jsx"},{"name":"Textarea","sourcePath":"components/forms/Textarea.jsx"},{"name":"Breadcrumbs","sourcePath":"components/navigation/Breadcrumbs.jsx"},{"name":"SideNav","sourcePath":"components/navigation/SideNav.jsx"},{"name":"Tabs","sourcePath":"components/navigation/Tabs.jsx"},{"name":"TopBar","sourcePath":"components/navigation/TopBar.jsx"}],"sourceHashes":{"components/core/Badge.jsx":"c926c022290b","components/core/Button.jsx":"e65fc544633a","components/core/Card.jsx":"87c6832cd748","components/core/Icon.jsx":"c5d246df0659","components/core/IconButton.jsx":"b0261f5cd35e","components/core/Logo.jsx":"c7ae134e344b","components/core/Tag.jsx":"8ac4d3a5b376","components/data/BarChart.jsx":"70019d7792a8","components/data/DataTable.jsx":"2a47fdae0ca2","components/data/ProgressBar.jsx":"ba8583ea0a06","components/data/StatCard.jsx":"6b329cdd3ee4","components/feedback/Alert.jsx":"4dcd696c33ba","components/feedback/Dialog.jsx":"61d610b9cdf7","components/feedback/Toast.jsx":"026d7db03e4c","components/feedback/Tooltip.jsx":"e2d5f2028372","components/forms/Checkbox.jsx":"43dc8ed1030c","components/forms/Field.jsx":"0bcea50260b3","components/forms/Input.jsx":"2c1c43686eaf","components/forms/Radio.jsx":"6ea11da5cdb7","components/forms/Select.jsx":"7c036749826c","components/forms/Switch.jsx":"e732732ce287","components/forms/Textarea.jsx":"b65bd7e89359","components/navigation/Breadcrumbs.jsx":"f09ce392afc8","components/navigation/SideNav.jsx":"957d2aa94172","components/navigation/Tabs.jsx":"39245dd4d31c","components/navigation/TopBar.jsx":"71832fceb48d","ui_kits/sistema/AppShell.jsx":"f317a65d5d5d","ui_kits/sistema/Dashboard.jsx":"f38f60c0b2f9","ui_kits/sistema/PatientDetail.jsx":"2150ff04bec6","ui_kits/sistema/PatientList.jsx":"644012dda92b","ui_kits/site/ContactPage.jsx":"a11f64ca5291","ui_kits/site/HomePage.jsx":"79b3ffe2edac","ui_kits/site/Shared.jsx":"9e1ba2d223bb","ui_kits/site/UnitsPage.jsx":"6be3af5a7f36"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.OpalusDesignSystem_2ac06f = window.OpalusDesignSystem_2ac06f || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Card.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const PADS = {
  sm: 16,
  md: 24,
  lg: 32
};
function Card({
  children,
  padding = "md",
  interactive,
  tone = "default",
  header,
  footer,
  style,
  onClick,
  ...rest
}) {
  const [h, setH] = React.useState(false);
  const p = PADS[padding] ?? PADS.md;
  const tones = {
    default: {
      background: "var(--surface-card)",
      border: "1px solid var(--border-default)",
      color: "var(--text-body)"
    },
    sunken: {
      background: "var(--surface-sunken)",
      border: "1px solid var(--border-muted)",
      color: "var(--text-body)"
    },
    brand: {
      background: "var(--gradient-navy)",
      border: "1px solid var(--navy-800)",
      color: "var(--text-inverse)"
    },
    accent: {
      background: "var(--navy-50)",
      border: "1px solid var(--navy-200)",
      color: "var(--text-body)"
    }
  }[tone];
  return /*#__PURE__*/React.createElement("div", _extends({
    onClick: onClick,
    onMouseEnter: () => setH(true),
    onMouseLeave: () => setH(false),
    style: {
      ...tones,
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
      boxShadow: interactive && h ? "var(--shadow-lg)" : "var(--shadow-sm)",
      transform: interactive && h ? "translateY(-2px)" : "none",
      cursor: interactive ? "pointer" : "default",
      transition: "box-shadow var(--duration-normal) var(--ease-standard),transform var(--duration-normal) var(--ease-standard)",
      ...style
    }
  }, rest), header && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: `${p}px ${p}px 0`
    }
  }, header), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: p
    }
  }, children), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: `0 ${p}px ${p}px`
    }
  }, footer));
}
Object.assign(__ds_scope, { Card });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Card.jsx", error: String((e && e.message) || e) }); }

// components/core/Icon.jsx
try { (() => {
/* Lucide (lucide.dev) is the Opalus icon set — 1.75px stroke, rounded caps, which matches
   the symbol's soft geometry. The brand supplied no icon library of its own.
   Host pages must load: https://unpkg.com/lucide@0.544.0/dist/umd/lucide.js */
function Icon({
  name,
  size = 20,
  strokeWidth = 1.75,
  color = "currentColor",
  style,
  ...rest
}) {
  const lib = typeof window !== "undefined" && window.lucide && window.lucide.icons;
  const toPascal = s => s.replace(/(^|-)([a-z])/g, (_, __, c) => c.toUpperCase());
  const node = lib && (lib[name] || lib[toPascal(name)]);
  const base = {
    width: size,
    height: size,
    flexShrink: 0,
    display: "block",
    ...style
  };
  if (!node) return React.createElement("span", {
    style: {
      ...base,
      borderRadius: 3,
      background: "var(--grey-200)"
    },
    ...rest
  });
  const [, attrs, children] = node;
  return React.createElement("svg", {
    ...attrs,
    width: size,
    height: size,
    stroke: color,
    strokeWidth,
    style: base,
    ...rest
  }, (children || []).map((c, i) => React.createElement(c[0], {
    key: i,
    ...c[1]
  })));
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/Badge.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const TONES = {
  neutral: ["var(--grey-100)", "var(--grey-700)"],
  brand: ["var(--navy-100)", "var(--navy-700)"],
  info: ["var(--blue-100)", "var(--blue-700)"],
  success: ["var(--teal-100)", "var(--teal-700)"],
  warning: ["var(--amber-100)", "var(--amber-700)"],
  danger: ["var(--red-100)", "var(--red-700)"],
  purple: ["var(--purple-100)", "var(--purple-700)"]
};
function Badge({
  children,
  tone = "neutral",
  icon,
  dot,
  size = "md",
  style,
  ...rest
}) {
  const [bg, fg] = TONES[tone] || TONES.neutral;
  const sm = size === "sm";
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 6,
      background: bg,
      color: fg,
      fontFamily: "var(--font-ui)",
      fontSize: sm ? "var(--text-3xs)" : "var(--text-2xs)",
      fontWeight: "var(--weight-semibold)",
      letterSpacing: "var(--tracking-wide)",
      textTransform: "uppercase",
      padding: sm ? "2px 8px" : "4px 10px",
      borderRadius: "var(--radius-full)",
      whiteSpace: "nowrap",
      ...style
    }
  }, rest), dot && /*#__PURE__*/React.createElement("span", {
    style: {
      width: 6,
      height: 6,
      borderRadius: 999,
      background: fg
    }
  }), icon && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: sm ? 11 : 13
  }), children);
}
Object.assign(__ds_scope, { Badge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Badge.jsx", error: String((e && e.message) || e) }); }

// components/core/Button.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: {
    height: 32,
    padding: "0 12px",
    fontSize: "var(--text-xs)",
    gap: 6,
    icon: 16
  },
  md: {
    height: 40,
    padding: "0 18px",
    fontSize: "var(--text-sm)",
    gap: 8,
    icon: 18
  },
  lg: {
    height: 48,
    padding: "0 26px",
    fontSize: "var(--text-md)",
    gap: 10,
    icon: 20
  }
};
const VARIANTS = {
  primary: {
    background: "var(--navy-700)",
    color: "var(--grey-0)",
    border: "1px solid var(--navy-700)",
    hover: "var(--navy-800)",
    active: "var(--navy-900)"
  },
  secondary: {
    background: "var(--grey-0)",
    color: "var(--navy-700)",
    border: "1px solid var(--grey-300)",
    hover: "var(--grey-50)",
    active: "var(--grey-100)"
  },
  accent: {
    background: "var(--blue-600)",
    color: "var(--grey-0)",
    border: "1px solid var(--blue-600)",
    hover: "var(--blue-700)",
    active: "var(--navy-700)"
  },
  ghost: {
    background: "transparent",
    color: "var(--navy-700)",
    border: "1px solid transparent",
    hover: "var(--navy-50)",
    active: "var(--navy-100)"
  },
  danger: {
    background: "var(--red-500)",
    color: "var(--grey-0)",
    border: "1px solid var(--red-500)",
    hover: "var(--red-700)",
    active: "var(--red-700)"
  },
  inverse: {
    background: "var(--grey-0)",
    color: "var(--navy-700)",
    border: "1px solid var(--grey-0)",
    hover: "var(--navy-100)",
    active: "var(--navy-200)"
  }
};
function Button({
  children,
  variant = "primary",
  size = "md",
  icon,
  iconAfter,
  disabled,
  fullWidth,
  type = "button",
  onClick,
  style,
  ...rest
}) {
  const [h, setH] = React.useState(false);
  const [a, setA] = React.useState(false);
  const s = SIZES[size] || SIZES.md;
  const v = VARIANTS[variant] || VARIANTS.primary;
  return /*#__PURE__*/React.createElement("button", _extends({
    type: type,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setH(true),
    onMouseLeave: () => {
      setH(false);
      setA(false);
    },
    onMouseDown: () => setA(true),
    onMouseUp: () => setA(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: s.gap,
      height: s.height,
      padding: s.padding,
      width: fullWidth ? "100%" : undefined,
      fontFamily: "var(--font-body)",
      fontSize: s.fontSize,
      fontWeight: "var(--weight-semibold)",
      letterSpacing: "var(--tracking-tight)",
      borderRadius: "var(--radius-md)",
      cursor: disabled ? "not-allowed" : "pointer",
      background: a ? v.active : h ? v.hover : v.background,
      color: v.color,
      border: v.border,
      boxShadow: variant === "primary" || variant === "accent" || variant === "danger" ? "var(--shadow-xs)" : "none",
      opacity: disabled ? 0.45 : 1,
      transition: "var(--transition-colors)",
      whiteSpace: "nowrap",
      ...style
    }
  }, rest), icon && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: s.icon
  }), children, iconAfter && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: iconAfter,
    size: s.icon
  }));
}
Object.assign(__ds_scope, { Button });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Button.jsx", error: String((e && e.message) || e) }); }

// components/core/IconButton.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: 30,
  md: 38,
  lg: 46
};
const GLYPH = {
  sm: 16,
  md: 18,
  lg: 22
};
function IconButton({
  icon,
  label,
  variant = "ghost",
  size = "md",
  disabled,
  active,
  onClick,
  style,
  ...rest
}) {
  const [h, setH] = React.useState(false);
  const box = SIZES[size] || SIZES.md;
  const tone = {
    ghost: {
      bg: active ? "var(--navy-100)" : h ? "var(--navy-50)" : "transparent",
      fg: "var(--navy-700)",
      bd: "1px solid transparent"
    },
    outline: {
      bg: h ? "var(--grey-50)" : "var(--grey-0)",
      fg: "var(--navy-700)",
      bd: "1px solid var(--grey-300)"
    },
    solid: {
      bg: h ? "var(--navy-800)" : "var(--navy-700)",
      fg: "var(--grey-0)",
      bd: "1px solid var(--navy-700)"
    },
    inverse: {
      bg: h ? "rgba(255,255,255,.18)" : "rgba(255,255,255,.08)",
      fg: "var(--grey-0)",
      bd: "1px solid rgba(255,255,255,.16)"
    }
  }[variant];
  return /*#__PURE__*/React.createElement("button", _extends({
    type: "button",
    "aria-label": label,
    disabled: disabled,
    onClick: onClick,
    onMouseEnter: () => setH(true),
    onMouseLeave: () => setH(false),
    style: {
      width: box,
      height: box,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "var(--radius-md)",
      background: tone.bg,
      color: tone.fg,
      border: tone.bd,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.45 : 1,
      transition: "var(--transition-colors)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: GLYPH[size] || 18
  }));
}
Object.assign(__ds_scope, { IconButton });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/IconButton.jsx", error: String((e && e.message) || e) }); }

// components/core/Logo.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const FILES = {
  color: {
    horizontal: "logo-horizontal.png",
    vertical: "logo-vertical.png",
    symbol: "symbol.png"
  },
  white: {
    horizontal: "logo-horizontal-white.png",
    vertical: "logo-vertical-white.png",
    symbol: "symbol-white.png"
  },
  mono: {
    horizontal: "logo-horizontal-mono.png",
    vertical: "logo-vertical-mono.png",
    symbol: "symbol-mono.png"
  }
};
function Logo({
  lockup = "horizontal",
  tone = "color",
  height = 32,
  base = "assets",
  style,
  ...rest
}) {
  const file = (FILES[tone] || FILES.color)[lockup] || FILES.color.horizontal;
  return /*#__PURE__*/React.createElement("img", _extends({
    src: `${base}/${file}`,
    alt: "Opalus",
    style: {
      height,
      width: "auto",
      display: "block",
      ...style
    }
  }, rest));
}
Object.assign(__ds_scope, { Logo });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Logo.jsx", error: String((e && e.message) || e) }); }

// components/core/Tag.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Tag({
  children,
  onRemove,
  selected,
  onClick,
  style,
  ...rest
}) {
  const [h, setH] = React.useState(false);
  const interactive = !!onClick;
  return /*#__PURE__*/React.createElement("span", _extends({
    onClick: onClick,
    onMouseEnter: () => setH(true),
    onMouseLeave: () => setH(false),
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 7,
      height: 28,
      padding: onRemove ? "0 6px 0 12px" : "0 12px",
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-xs)",
      fontWeight: "var(--weight-medium)",
      borderRadius: "var(--radius-full)",
      cursor: interactive ? "pointer" : "default",
      background: selected ? "var(--navy-700)" : h && interactive ? "var(--grey-100)" : "var(--grey-50)",
      color: selected ? "var(--grey-0)" : "var(--text-body)",
      border: selected ? "1px solid var(--navy-700)" : "1px solid var(--grey-200)",
      transition: "var(--transition-colors)",
      ...style
    }
  }, rest), children, onRemove && /*#__PURE__*/React.createElement("button", {
    type: "button",
    "aria-label": "Remover",
    onClick: e => {
      e.stopPropagation();
      onRemove(e);
    },
    style: {
      display: "inline-flex",
      border: 0,
      background: "transparent",
      padding: 2,
      borderRadius: 999,
      color: "inherit",
      cursor: "pointer",
      opacity: 0.6
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "x",
    size: 13
  })));
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tag.jsx", error: String((e && e.message) || e) }); }

// components/data/BarChart.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SEQ = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)", "var(--chart-6)", "var(--chart-7)", "var(--chart-8)"];
function BarChart({
  data = [],
  height = 180,
  color,
  showValues,
  style,
  ...rest
}) {
  const max = Math.max(1, ...data.map(d => d.value));
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 10,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-end",
      gap: 10,
      height,
      borderBottom: "1px solid var(--chart-grid)",
      paddingBottom: 1
    }
  }, data.map((d, i) => /*#__PURE__*/React.createElement("div", {
    key: d.label,
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      justifyContent: "flex-end",
      alignItems: "center",
      gap: 6,
      height: "100%"
    }
  }, showValues && /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-ui)",
      fontSize: "var(--text-3xs)",
      fontWeight: 600,
      fontVariantNumeric: "tabular-nums",
      color: "var(--text-secondary)"
    }
  }, d.value), /*#__PURE__*/React.createElement("div", {
    style: {
      width: "100%",
      height: `${d.value / max * 100}%`,
      background: d.color || color || SEQ[i % SEQ.length],
      borderRadius: "var(--radius-sm) var(--radius-sm) 0 0",
      transition: "height var(--duration-slow) var(--ease-standard)"
    }
  })))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 10
    }
  }, data.map(d => /*#__PURE__*/React.createElement("span", {
    key: d.label,
    style: {
      flex: 1,
      textAlign: "center",
      fontFamily: "var(--font-ui)",
      fontSize: "var(--text-3xs)",
      color: "var(--text-tertiary)",
      letterSpacing: "var(--tracking-wide)",
      textTransform: "uppercase"
    }
  }, d.label))));
}
Object.assign(__ds_scope, { BarChart });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/BarChart.jsx", error: String((e && e.message) || e) }); }

// components/data/DataTable.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function DataTable({
  columns = [],
  rows = [],
  dense,
  onRowClick,
  style,
  ...rest
}) {
  const [hover, setHover] = React.useState(-1);
  const pad = dense ? "8px 14px" : "13px 16px";
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      background: "var(--surface-card)",
      border: "1px solid var(--border-default)",
      borderRadius: "var(--radius-lg)",
      overflow: "hidden",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("table", {
    style: {
      width: "100%",
      borderCollapse: "collapse"
    }
  }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", {
    style: {
      background: "var(--surface-sunken)"
    }
  }, columns.map(c => /*#__PURE__*/React.createElement("th", {
    key: c.key,
    style: {
      textAlign: c.align || "left",
      padding: pad,
      fontFamily: "var(--font-ui)",
      fontSize: "var(--text-3xs)",
      fontWeight: 600,
      letterSpacing: "var(--tracking-widest)",
      textTransform: "uppercase",
      color: "var(--text-secondary)",
      whiteSpace: "nowrap",
      borderBottom: "1px solid var(--border-default)",
      width: c.width
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 5
    }
  }, c.label, c.sorted && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: c.sorted === "desc" ? "arrow-down" : "arrow-up",
    size: 12
  })))))), /*#__PURE__*/React.createElement("tbody", null, rows.map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: r.id ?? i,
    onClick: () => onRowClick && onRowClick(r),
    onMouseEnter: () => setHover(i),
    onMouseLeave: () => setHover(-1),
    style: {
      background: hover === i ? "var(--surface-hover)" : "transparent",
      cursor: onRowClick ? "pointer" : "default",
      transition: "background-color var(--duration-fast) var(--ease-standard)"
    }
  }, columns.map(c => /*#__PURE__*/React.createElement("td", {
    key: c.key,
    style: {
      textAlign: c.align || "left",
      padding: pad,
      fontFamily: "var(--font-body)",
      fontSize: dense ? "var(--text-xs)" : "var(--text-sm)",
      color: "var(--text-body)",
      borderBottom: i === rows.length - 1 ? "none" : "1px solid var(--border-muted)",
      fontVariantNumeric: c.numeric ? "tabular-nums" : undefined,
      fontFamily: c.numeric ? "var(--font-ui)" : "var(--font-body)"
    }
  }, r[c.key])))))));
}
Object.assign(__ds_scope, { DataTable });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/DataTable.jsx", error: String((e && e.message) || e) }); }

// components/data/ProgressBar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function ProgressBar({
  value = 0,
  max = 100,
  label,
  showValue,
  tone = "brand",
  size = "md",
  style,
  ...rest
}) {
  const pct = Math.max(0, Math.min(100, value / max * 100));
  const fill = {
    brand: "var(--navy-700)",
    accent: "var(--blue-600)",
    success: "var(--teal-500)",
    warning: "var(--amber-500)",
    danger: "var(--red-500)"
  }[tone];
  const h = size === "sm" ? 5 : size === "lg" ? 12 : 8;
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 7,
      ...style
    }
  }, rest), (label || showValue) && /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      fontFamily: "var(--font-ui)",
      fontSize: "var(--text-2xs)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 600,
      letterSpacing: "var(--tracking-wide)",
      textTransform: "uppercase",
      color: "var(--text-secondary)"
    }
  }, label), showValue && /*#__PURE__*/React.createElement("span", {
    style: {
      fontVariantNumeric: "tabular-nums",
      color: "var(--text-primary)",
      fontWeight: 600
    }
  }, Math.round(pct), "%")), /*#__PURE__*/React.createElement("div", {
    style: {
      height: h,
      borderRadius: 999,
      background: "var(--grey-100)",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: `${pct}%`,
      height: "100%",
      borderRadius: 999,
      background: fill,
      transition: "width var(--duration-slow) var(--ease-standard)"
    }
  })));
}
Object.assign(__ds_scope, { ProgressBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/ProgressBar.jsx", error: String((e && e.message) || e) }); }

// components/data/StatCard.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function StatCard({
  label,
  value,
  unit,
  delta,
  deltaTone,
  icon,
  footnote,
  tone = "default",
  style,
  ...rest
}) {
  const dark = tone === "brand";
  const up = typeof delta === "string" && delta.trim().startsWith("+");
  const dt = deltaTone || (up ? "success" : "danger");
  const dc = {
    success: "var(--teal-500)",
    danger: "var(--red-500)",
    neutral: "var(--text-secondary)"
  }[dt];
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 12,
      padding: 20,
      background: dark ? "var(--gradient-navy)" : "var(--surface-card)",
      border: dark ? "1px solid var(--navy-800)" : "1px solid var(--border-default)",
      borderRadius: "var(--radius-lg)",
      boxShadow: "var(--shadow-sm)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8
    }
  }, icon && /*#__PURE__*/React.createElement("span", {
    style: {
      color: dark ? "var(--navy-300)" : "var(--navy-400)"
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 16
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-ui)",
      fontSize: "var(--text-2xs)",
      fontWeight: 600,
      letterSpacing: "var(--tracking-wide)",
      textTransform: "uppercase",
      color: dark ? "var(--text-inverse-muted)" : "var(--text-secondary)"
    }
  }, label)), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "baseline",
      gap: 8
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      fontFamily: "var(--font-ui)",
      fontSize: "var(--text-4xl)",
      fontWeight: 600,
      fontVariantNumeric: "tabular-nums",
      letterSpacing: "var(--tracking-tight)",
      lineHeight: 1,
      color: dark ? "var(--grey-0)" : "var(--navy-700)"
    }
  }, value), unit && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: "var(--text-sm)",
      color: dark ? "var(--text-inverse-muted)" : "var(--text-tertiary)"
    }
  }, unit), delta && /*#__PURE__*/React.createElement("span", {
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 3,
      marginLeft: 2,
      fontFamily: "var(--font-ui)",
      fontSize: "var(--text-xs)",
      fontWeight: 600,
      color: dc
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: up ? "trending-up" : "trending-down",
    size: 14
  }), delta)), footnote && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: "var(--text-2xs)",
      color: dark ? "rgba(255,255,255,.55)" : "var(--text-tertiary)"
    }
  }, footnote));
}
Object.assign(__ds_scope, { StatCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/StatCard.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Alert.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const TONES = {
  info: ["var(--blue-50)", "var(--blue-200)", "var(--blue-700)", "info"],
  success: ["var(--teal-50)", "var(--teal-100)", "var(--teal-700)", "check-circle"],
  warning: ["var(--amber-100)", "#f0dcb0", "var(--amber-700)", "alert-triangle"],
  danger: ["var(--red-100)", "#f2c4c1", "var(--red-700)", "alert-octagon"]
};
function Alert({
  title,
  children,
  tone = "info",
  icon,
  onClose,
  style,
  ...rest
}) {
  const [bg, bd, fg, defIcon] = TONES[tone] || TONES.info;
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "status",
    style: {
      display: "flex",
      gap: 12,
      padding: "14px 16px",
      background: bg,
      border: `1px solid ${bd}`,
      borderRadius: "var(--radius-md)",
      color: fg,
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      marginTop: 1
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon || defIcon,
    size: 18
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-sm)",
      fontWeight: "var(--weight-semibold)",
      marginBottom: children ? 3 : 0
    }
  }, title), children && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-xs)",
      lineHeight: "var(--leading-normal)",
      opacity: 0.92
    }
  }, children)), onClose && /*#__PURE__*/React.createElement("button", {
    type: "button",
    "aria-label": "Fechar",
    onClick: onClose,
    style: {
      border: 0,
      background: "transparent",
      color: "inherit",
      cursor: "pointer",
      opacity: 0.6,
      padding: 0,
      height: 18
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "x",
    size: 16
  })));
}
Object.assign(__ds_scope, { Alert });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Alert.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Dialog.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Dialog({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  width = 520,
  style,
  ...rest
}) {
  if (!open) return null;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "fixed",
      inset: 0,
      zIndex: 60,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
      background: "var(--surface-overlay)",
      backdropFilter: "blur(3px)"
    },
    onClick: onClose
  }, /*#__PURE__*/React.createElement("div", _extends({
    role: "dialog",
    "aria-modal": "true",
    onClick: e => e.stopPropagation(),
    style: {
      width: "100%",
      maxWidth: width,
      background: "var(--surface-card)",
      borderRadius: "var(--radius-xl)",
      boxShadow: "var(--shadow-xl)",
      overflow: "hidden",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-start",
      gap: 16,
      padding: "24px 24px 0"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: "var(--text-xl)",
      fontWeight: "var(--weight-bold)",
      color: "var(--text-primary)",
      margin: 0,
      letterSpacing: "var(--tracking-tight)"
    }
  }, title), description && /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "6px 0 0",
      fontSize: "var(--text-sm)",
      color: "var(--text-secondary)"
    }
  }, description)), onClose && /*#__PURE__*/React.createElement("button", {
    type: "button",
    "aria-label": "Fechar",
    onClick: onClose,
    style: {
      border: 0,
      background: "transparent",
      color: "var(--text-tertiary)",
      cursor: "pointer",
      padding: 2
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "x",
    size: 20
  }))), children && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "20px 24px 0",
      fontSize: "var(--text-sm)",
      color: "var(--text-body)"
    }
  }, children), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "flex-end",
      gap: 10,
      padding: 24
    }
  }, footer)));
}
Object.assign(__ds_scope, { Dialog });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Dialog.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Toast.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const ICONS = {
  info: "info",
  success: "check-circle",
  warning: "alert-triangle",
  danger: "alert-octagon"
};
const ACCENT = {
  info: "var(--blue-300)",
  success: "var(--teal-300)",
  warning: "var(--amber-500)",
  danger: "var(--red-500)"
};
function Toast({
  title,
  children,
  tone = "info",
  onClose,
  action,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    role: "status",
    style: {
      display: "flex",
      gap: 12,
      alignItems: "flex-start",
      minWidth: 300,
      maxWidth: 420,
      padding: "14px 16px",
      background: "var(--navy-800)",
      color: "var(--text-inverse)",
      borderRadius: "var(--radius-md)",
      boxShadow: "var(--shadow-xl)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("span", {
    style: {
      color: ACCENT[tone],
      marginTop: 1
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: ICONS[tone],
    size: 18
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, title && /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-sm)",
      fontWeight: "var(--weight-semibold)"
    }
  }, title), children && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-xs)",
      color: "var(--text-inverse-muted)",
      marginTop: 3
    }
  }, children), action && /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 10
    }
  }, action)), onClose && /*#__PURE__*/React.createElement("button", {
    type: "button",
    "aria-label": "Fechar",
    onClick: onClose,
    style: {
      border: 0,
      background: "transparent",
      color: "rgba(255,255,255,.6)",
      cursor: "pointer",
      padding: 0,
      height: 18
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "x",
    size: 16
  })));
}
Object.assign(__ds_scope, { Toast });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Toast.jsx", error: String((e && e.message) || e) }); }

// components/feedback/Tooltip.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Tooltip({
  label,
  children,
  placement = "top",
  style,
  ...rest
}) {
  const [open, setOpen] = React.useState(false);
  const pos = {
    top: {
      bottom: "calc(100% + 8px)",
      left: "50%",
      transform: "translateX(-50%)"
    },
    bottom: {
      top: "calc(100% + 8px)",
      left: "50%",
      transform: "translateX(-50%)"
    },
    left: {
      right: "calc(100% + 8px)",
      top: "50%",
      transform: "translateY(-50%)"
    },
    right: {
      left: "calc(100% + 8px)",
      top: "50%",
      transform: "translateY(-50%)"
    }
  }[placement];
  return /*#__PURE__*/React.createElement("span", _extends({
    style: {
      position: "relative",
      display: "inline-flex",
      ...style
    },
    onMouseEnter: () => setOpen(true),
    onMouseLeave: () => setOpen(false),
    onFocus: () => setOpen(true),
    onBlur: () => setOpen(false)
  }, rest), children, /*#__PURE__*/React.createElement("span", {
    role: "tooltip",
    style: {
      position: "absolute",
      ...pos,
      zIndex: 30,
      pointerEvents: "none",
      background: "var(--navy-800)",
      color: "var(--grey-0)",
      padding: "6px 10px",
      borderRadius: "var(--radius-sm)",
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-2xs)",
      whiteSpace: "nowrap",
      boxShadow: "var(--shadow-md)",
      opacity: open ? 1 : 0,
      transition: "opacity var(--duration-fast) var(--ease-standard)"
    }
  }, label));
}
Object.assign(__ds_scope, { Tooltip });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/Tooltip.jsx", error: String((e && e.message) || e) }); }

// components/forms/Checkbox.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Checkbox({
  label,
  checked,
  indeterminate,
  disabled,
  onChange,
  style,
  ...rest
}) {
  const on = checked || indeterminate;
  return /*#__PURE__*/React.createElement("label", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-sm)",
      color: "var(--text-body)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    checked: !!checked,
    disabled: disabled,
    onChange: onChange,
    style: {
      position: "absolute",
      opacity: 0,
      width: 0,
      height: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      flexShrink: 0,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: "var(--radius-xs)",
      background: on ? "var(--navy-700)" : "var(--grey-0)",
      border: on ? "1px solid var(--navy-700)" : "1px solid var(--grey-300)",
      color: "var(--grey-0)",
      transition: "var(--transition-colors)"
    }
  }, indeterminate ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "minus",
    size: 13,
    strokeWidth: 3
  }) : checked ? /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "check",
    size: 13,
    strokeWidth: 3
  }) : null), label);
}
Object.assign(__ds_scope, { Checkbox });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Checkbox.jsx", error: String((e && e.message) || e) }); }

// components/forms/Field.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Field({
  label,
  hint,
  error,
  required,
  htmlFor,
  children,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 6,
      ...style
    }
  }, rest), label && /*#__PURE__*/React.createElement("label", {
    htmlFor: htmlFor,
    style: {
      fontFamily: "var(--font-ui)",
      fontSize: "var(--text-2xs)",
      fontWeight: "var(--weight-semibold)",
      letterSpacing: "var(--tracking-wide)",
      textTransform: "uppercase",
      color: "var(--text-secondary)"
    }
  }, label, required && /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--danger)",
      marginLeft: 3
    }
  }, "*")), children, (error || hint) && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: "var(--text-xs)",
      color: error ? "var(--danger-text)" : "var(--text-tertiary)"
    }
  }, error || hint));
}
Object.assign(__ds_scope, { Field });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Field.jsx", error: String((e && e.message) || e) }); }

// components/forms/Input.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: 34,
  md: 42,
  lg: 50
};
function Input({
  icon,
  iconAfter,
  invalid,
  disabled,
  size = "md",
  style,
  ...rest
}) {
  const [f, setF] = React.useState(false);
  const h = SIZES[size] || SIZES.md;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      height: h,
      padding: "0 12px",
      background: disabled ? "var(--grey-50)" : "var(--grey-0)",
      borderRadius: "var(--radius-md)",
      border: `1px solid ${invalid ? "var(--danger)" : f ? "var(--border-focus)" : "var(--border-default)"}`,
      boxShadow: f ? invalid ? "var(--shadow-focus-danger)" : "var(--shadow-focus)" : "none",
      transition: "var(--transition-colors)",
      ...style
    }
  }, icon && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: icon,
    size: 16,
    color: "var(--text-tertiary)"
  }), /*#__PURE__*/React.createElement("input", _extends({
    disabled: disabled,
    onFocus: () => setF(true),
    onBlur: () => setF(false),
    style: {
      flex: 1,
      minWidth: 0,
      border: 0,
      outline: "none",
      background: "transparent",
      fontFamily: "var(--font-body)",
      fontSize: size === "sm" ? "var(--text-xs)" : "var(--text-sm)",
      color: "var(--text-primary)"
    }
  }, rest)), iconAfter && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: iconAfter,
    size: 16,
    color: "var(--text-tertiary)"
  }));
}
Object.assign(__ds_scope, { Input });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Input.jsx", error: String((e && e.message) || e) }); }

// components/forms/Radio.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Radio({
  label,
  checked,
  disabled,
  name,
  value,
  onChange,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-sm)",
      color: "var(--text-body)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("input", {
    type: "radio",
    name: name,
    value: value,
    checked: !!checked,
    disabled: disabled,
    onChange: onChange,
    style: {
      position: "absolute",
      opacity: 0,
      width: 0,
      height: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      flexShrink: 0,
      borderRadius: 999,
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      background: "var(--grey-0)",
      border: checked ? "5px solid var(--navy-700)" : "1px solid var(--grey-300)",
      transition: "var(--transition-colors)"
    }
  }), label);
}
Object.assign(__ds_scope, { Radio });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Radio.jsx", error: String((e && e.message) || e) }); }

// components/forms/Select.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
const SIZES = {
  sm: 34,
  md: 42,
  lg: 50
};
function Select({
  options = [],
  placeholder,
  invalid,
  disabled,
  size = "md",
  style,
  ...rest
}) {
  const [f, setF] = React.useState(false);
  const h = SIZES[size] || SIZES.md;
  return /*#__PURE__*/React.createElement("div", {
    style: {
      position: "relative",
      display: "flex",
      alignItems: "center",
      height: h,
      background: disabled ? "var(--grey-50)" : "var(--grey-0)",
      borderRadius: "var(--radius-md)",
      border: `1px solid ${invalid ? "var(--danger)" : f ? "var(--border-focus)" : "var(--border-default)"}`,
      boxShadow: f ? "var(--shadow-focus)" : "none",
      transition: "var(--transition-colors)",
      ...style
    }
  }, /*#__PURE__*/React.createElement("select", _extends({
    disabled: disabled,
    onFocus: () => setF(true),
    onBlur: () => setF(false),
    style: {
      appearance: "none",
      width: "100%",
      height: "100%",
      border: 0,
      outline: "none",
      background: "transparent",
      padding: "0 34px 0 12px",
      fontFamily: "var(--font-body)",
      fontSize: size === "sm" ? "var(--text-xs)" : "var(--text-sm)",
      color: "var(--text-primary)",
      cursor: "pointer"
    }
  }, rest), placeholder && /*#__PURE__*/React.createElement("option", {
    value: ""
  }, placeholder), options.map(o => {
    const v = typeof o === "string" ? o : o.value;
    const l = typeof o === "string" ? o : o.label;
    return /*#__PURE__*/React.createElement("option", {
      key: v,
      value: v
    }, l);
  })), /*#__PURE__*/React.createElement("span", {
    style: {
      position: "absolute",
      right: 11,
      pointerEvents: "none",
      color: "var(--text-tertiary)"
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
    name: "chevron-down",
    size: 16
  })));
}
Object.assign(__ds_scope, { Select });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Select.jsx", error: String((e && e.message) || e) }); }

// components/forms/Switch.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Switch({
  label,
  checked,
  disabled,
  onChange,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("label", _extends({
    style: {
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      cursor: disabled ? "not-allowed" : "pointer",
      opacity: disabled ? 0.5 : 1,
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-sm)",
      color: "var(--text-body)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    role: "switch",
    checked: !!checked,
    disabled: disabled,
    onChange: onChange,
    style: {
      position: "absolute",
      opacity: 0,
      width: 0,
      height: 0
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      width: 38,
      height: 22,
      flexShrink: 0,
      borderRadius: 999,
      padding: 2,
      background: checked ? "var(--teal-500)" : "var(--grey-300)",
      display: "inline-flex",
      transition: "background-color var(--duration-normal) var(--ease-standard)"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 18,
      height: 18,
      borderRadius: 999,
      background: "var(--grey-0)",
      boxShadow: "var(--shadow-xs)",
      transform: checked ? "translateX(16px)" : "translateX(0)",
      transition: "transform var(--duration-normal) var(--ease-standard)"
    }
  })), label);
}
Object.assign(__ds_scope, { Switch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Switch.jsx", error: String((e && e.message) || e) }); }

// components/forms/Textarea.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Textarea({
  invalid,
  disabled,
  rows = 4,
  style,
  ...rest
}) {
  const [f, setF] = React.useState(false);
  return /*#__PURE__*/React.createElement("textarea", _extends({
    rows: rows,
    disabled: disabled,
    onFocus: () => setF(true),
    onBlur: () => setF(false),
    style: {
      width: "100%",
      padding: "10px 12px",
      resize: "vertical",
      outline: "none",
      background: disabled ? "var(--grey-50)" : "var(--grey-0)",
      borderRadius: "var(--radius-md)",
      border: `1px solid ${invalid ? "var(--danger)" : f ? "var(--border-focus)" : "var(--border-default)"}`,
      boxShadow: f ? "var(--shadow-focus)" : "none",
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-sm)",
      lineHeight: "var(--leading-normal)",
      color: "var(--text-primary)",
      transition: "var(--transition-colors)",
      ...style
    }
  }, rest));
}
Object.assign(__ds_scope, { Textarea });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/forms/Textarea.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Breadcrumbs.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Breadcrumbs({
  items = [],
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("nav", _extends({
    style: {
      display: "flex",
      alignItems: "center",
      gap: 8,
      fontFamily: "var(--font-body)",
      fontSize: "var(--text-xs)",
      ...style
    }
  }, rest), items.map((it, i) => {
    const last = i === items.length - 1;
    const label = typeof it === "string" ? it : it.label;
    const href = typeof it === "string" ? undefined : it.href;
    return /*#__PURE__*/React.createElement(React.Fragment, {
      key: label
    }, last ? /*#__PURE__*/React.createElement("span", {
      style: {
        color: "var(--text-primary)",
        fontWeight: "var(--weight-semibold)"
      }
    }, label) : /*#__PURE__*/React.createElement("a", {
      href: href || "#",
      style: {
        color: "var(--text-secondary)"
      }
    }, label), !last && /*#__PURE__*/React.createElement("span", {
      style: {
        color: "var(--grey-300)",
        display: "inline-flex"
      }
    }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
      name: "chevron-right",
      size: 13
    })));
  }));
}
Object.assign(__ds_scope, { Breadcrumbs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Breadcrumbs.jsx", error: String((e && e.message) || e) }); }

// components/navigation/SideNav.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function SideNav({
  items = [],
  value,
  onChange,
  footer,
  assetBase = "assets",
  width = 248,
  style,
  ...rest
}) {
  return /*#__PURE__*/React.createElement("nav", _extends({
    style: {
      width,
      flexShrink: 0,
      background: "var(--navy-800)",
      color: "var(--text-inverse)",
      display: "flex",
      flexDirection: "column",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement("div", {
    style: {
      padding: "22px 20px 26px"
    }
  }, /*#__PURE__*/React.createElement(__ds_scope.Logo, {
    tone: "white",
    height: 26,
    base: assetBase
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      gap: 2,
      padding: "0 12px",
      overflow: "auto"
    }
  }, items.map(it => {
    if (it.section) return /*#__PURE__*/React.createElement("div", {
      key: it.section,
      style: {
        fontFamily: "var(--font-ui)",
        fontSize: "var(--text-3xs)",
        fontWeight: 600,
        letterSpacing: "var(--tracking-widest)",
        textTransform: "uppercase",
        color: "rgba(255,255,255,.42)",
        padding: "18px 10px 7px"
      }
    }, it.section);
    const on = it.id === value;
    return /*#__PURE__*/React.createElement("button", {
      key: it.id,
      type: "button",
      onClick: () => onChange && onChange(it.id),
      style: {
        display: "flex",
        alignItems: "center",
        gap: 11,
        width: "100%",
        height: 40,
        padding: "0 10px",
        border: 0,
        borderRadius: "var(--radius-md)",
        cursor: "pointer",
        textAlign: "left",
        background: on ? "rgba(255,255,255,.12)" : "transparent",
        color: on ? "var(--grey-0)" : "rgba(255,255,255,.72)",
        fontFamily: "var(--font-body)",
        fontSize: "var(--text-sm)",
        fontWeight: on ? "var(--weight-semibold)" : "var(--weight-regular)",
        transition: "var(--transition-colors)"
      }
    }, /*#__PURE__*/React.createElement(__ds_scope.Icon, {
      name: it.icon,
      size: 18
    }), /*#__PURE__*/React.createElement("span", {
      style: {
        flex: 1
      }
    }, it.label), it.count != null && /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: "var(--font-ui)",
        fontSize: "var(--text-3xs)",
        fontWeight: 600,
        background: "var(--teal-500)",
        color: "var(--grey-0)",
        padding: "1px 7px",
        borderRadius: 999
      }
    }, it.count));
  })), footer && /*#__PURE__*/React.createElement("div", {
    style: {
      padding: 16,
      borderTop: "1px solid rgba(255,255,255,.1)"
    }
  }, footer));
}
Object.assign(__ds_scope, { SideNav });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/SideNav.jsx", error: String((e && e.message) || e) }); }

// components/navigation/Tabs.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function Tabs({
  items = [],
  value,
  onChange,
  variant = "underline",
  style,
  ...rest
}) {
  const active = value ?? (items[0] && (items[0].id || items[0]));
  const norm = items.map(i => typeof i === "string" ? {
    id: i,
    label: i
  } : i);
  if (variant === "pill") {
    return /*#__PURE__*/React.createElement("div", _extends({
      style: {
        display: "inline-flex",
        gap: 4,
        padding: 4,
        background: "var(--grey-100)",
        borderRadius: "var(--radius-md)",
        ...style
      }
    }, rest), norm.map(t => {
      const on = t.id === active;
      return /*#__PURE__*/React.createElement("button", {
        key: t.id,
        type: "button",
        onClick: () => onChange && onChange(t.id),
        style: {
          display: "inline-flex",
          alignItems: "center",
          gap: 7,
          height: 32,
          padding: "0 14px",
          border: 0,
          borderRadius: "var(--radius-sm)",
          cursor: "pointer",
          fontFamily: "var(--font-body)",
          fontSize: "var(--text-xs)",
          fontWeight: "var(--weight-semibold)",
          background: on ? "var(--grey-0)" : "transparent",
          color: on ? "var(--navy-700)" : "var(--text-secondary)",
          boxShadow: on ? "var(--shadow-xs)" : "none",
          transition: "var(--transition-colors)"
        }
      }, t.icon && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
        name: t.icon,
        size: 15
      }), t.label);
    }));
  }
  return /*#__PURE__*/React.createElement("div", _extends({
    style: {
      display: "flex",
      gap: 28,
      borderBottom: "1px solid var(--border-default)",
      ...style
    }
  }, rest), norm.map(t => {
    const on = t.id === active;
    return /*#__PURE__*/React.createElement("button", {
      key: t.id,
      type: "button",
      onClick: () => onChange && onChange(t.id),
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "0 0 12px",
        border: 0,
        background: "transparent",
        cursor: "pointer",
        fontFamily: "var(--font-body)",
        fontSize: "var(--text-sm)",
        fontWeight: on ? "var(--weight-semibold)" : "var(--weight-medium)",
        color: on ? "var(--navy-700)" : "var(--text-secondary)",
        boxShadow: on ? "inset 0 -2px 0 var(--navy-700)" : "none",
        transition: "var(--transition-colors)"
      }
    }, t.icon && /*#__PURE__*/React.createElement(__ds_scope.Icon, {
      name: t.icon,
      size: 16
    }), t.label, t.count != null && /*#__PURE__*/React.createElement("span", {
      style: {
        fontFamily: "var(--font-ui)",
        fontSize: "var(--text-3xs)",
        fontWeight: 600,
        background: on ? "var(--navy-100)" : "var(--grey-100)",
        color: on ? "var(--navy-700)" : "var(--text-secondary)",
        padding: "1px 7px",
        borderRadius: 999
      }
    }, t.count));
  }));
}
Object.assign(__ds_scope, { Tabs });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/Tabs.jsx", error: String((e && e.message) || e) }); }

// components/navigation/TopBar.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function TopBar({
  links = [],
  active,
  onNavigate,
  action,
  tone = "light",
  assetBase = "assets",
  style,
  ...rest
}) {
  const dark = tone === "dark";
  return /*#__PURE__*/React.createElement("header", _extends({
    style: {
      display: "flex",
      alignItems: "center",
      gap: 32,
      height: 72,
      padding: "0 32px",
      background: dark ? "var(--navy-700)" : "var(--glass)",
      backdropFilter: dark ? undefined : "var(--glass-blur)",
      borderBottom: dark ? "1px solid var(--navy-800)" : "1px solid var(--border-default)",
      ...style
    }
  }, rest), /*#__PURE__*/React.createElement(__ds_scope.Logo, {
    tone: dark ? "white" : "color",
    height: 28,
    base: assetBase
  }), /*#__PURE__*/React.createElement("nav", {
    style: {
      display: "flex",
      gap: 26,
      flex: 1
    }
  }, links.map(l => {
    const label = typeof l === "string" ? l : l.label;
    const on = label === active;
    return /*#__PURE__*/React.createElement("a", {
      key: label,
      href: typeof l === "object" && l.href || "#",
      onClick: e => {
        if (onNavigate) {
          e.preventDefault();
          onNavigate(label);
        }
      },
      style: {
        fontFamily: "var(--font-body)",
        fontSize: "var(--text-sm)",
        fontWeight: on ? "var(--weight-semibold)" : "var(--weight-medium)",
        textDecoration: "none",
        color: dark ? on ? "var(--grey-0)" : "rgba(255,255,255,.75)" : on ? "var(--navy-700)" : "var(--text-secondary)"
      }
    }, label);
  })), action);
}
Object.assign(__ds_scope, { TopBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/TopBar.jsx", error: String((e && e.message) || e) }); }

// ui_kits/sistema/AppShell.jsx
try { (() => {
const {
  SideNav,
  IconButton,
  Icon,
  Input,
  Badge,
  Button,
  Logo
} = window.OpalusDesignSystem_2ac06f;
const NAV = [{
  section: "Assistencial"
}, {
  id: "dash",
  label: "Painel",
  icon: "layout-dashboard"
}, {
  id: "pacientes",
  label: "Residentes",
  icon: "users",
  count: 8
}, {
  id: "prescricoes",
  label: "Prescrições",
  icon: "clipboard-list"
}, {
  section: "Gestão"
}, {
  id: "indicadores",
  label: "Indicadores",
  icon: "activity"
}, {
  id: "leitos",
  label: "Leitos",
  icon: "bed-double"
}, {
  id: "config",
  label: "Configurações",
  icon: "settings"
}];
function AppHeader({
  title,
  subtitle,
  actions,
  onSearch
}) {
  return /*#__PURE__*/React.createElement("header", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 20,
      padding: "18px 28px",
      background: "var(--surface-card)",
      borderBottom: "1px solid var(--border-default)"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      minWidth: 0
    }
  }, /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 24,
      fontWeight: 700,
      letterSpacing: "-.015em",
      color: "var(--text-primary)",
      margin: 0
    }
  }, title), subtitle && /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-xs)",
      color: "var(--text-tertiary)",
      marginTop: 3
    }
  }, subtitle)), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 260
    }
  }, /*#__PURE__*/React.createElement(Input, {
    size: "sm",
    icon: "search",
    placeholder: "Buscar residente, leito\u2026",
    onChange: onSearch
  })), actions, /*#__PURE__*/React.createElement(IconButton, {
    icon: "bell",
    label: "Notifica\xE7\xF5es",
    variant: "outline"
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 9,
      paddingLeft: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 34,
      height: 34,
      borderRadius: 999,
      background: "var(--gradient-symbol)",
      color: "var(--grey-0)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "var(--font-ui)",
      fontSize: 13,
      fontWeight: 600
    }
  }, "RC"), /*#__PURE__*/React.createElement("div", {
    style: {
      lineHeight: 1.25
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-xs)",
      fontWeight: 600,
      color: "var(--text-primary)"
    }
  }, "Renata Costa"), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-3xs)",
      color: "var(--text-tertiary)"
    }
  }, "Enfermeira-chefe"))));
}
function AppShell({
  nav,
  onNav,
  children
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      height: "100vh",
      overflow: "hidden",
      background: "var(--surface-page)"
    }
  }, /*#__PURE__*/React.createElement(SideNav, {
    items: NAV,
    value: nav,
    onChange: onNav,
    assetBase: "../../assets",
    footer: /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: 10,
        color: "rgba(255,255,255,.6)",
        fontSize: "var(--text-2xs)"
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "life-buoy",
      size: 16
    }), " Suporte \xB7 ramal 4400")
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      display: "flex",
      flexDirection: "column",
      minWidth: 0
    }
  }, children));
}
Object.assign(window, {
  AppShell,
  AppHeader,
  NAV
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/sistema/AppShell.jsx", error: String((e && e.message) || e) }); }

// ui_kits/sistema/Dashboard.jsx
try { (() => {
const {
  StatCard,
  Card,
  BarChart,
  ProgressBar,
  Badge,
  DataTable,
  Tabs,
  Button,
  Alert,
  Icon
} = window.OpalusDesignSystem_2ac06f;
function Dashboard({
  onOpenPatient
}) {
  const [range, setRange] = React.useState("Semana");
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: "auto",
      padding: 28,
      display: "flex",
      flexDirection: "column",
      gap: 20
    }
  }, /*#__PURE__*/React.createElement(Alert, {
    tone: "warning",
    title: "3 prescri\xE7\xF5es vencem hoje",
    onClose: () => {}
  }, "Ala Norte \u2014 revise antes das 18h."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(4,1fr)",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(StatCard, {
    label: "Ocupa\xE7\xE3o",
    value: "92,4",
    unit: "%",
    delta: "+4,2 p.p.",
    icon: "bed-double",
    footnote: "\xDAltimas 24h"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Residentes ativos",
    value: "1.284",
    delta: "+12",
    icon: "users",
    footnote: "4 unidades"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Tempo m\xE9dio",
    value: "12,4",
    unit: "dias",
    delta: "-1,1",
    icon: "clock",
    footnote: "Interna\xE7\xE3o cl\xEDnica"
  }), /*#__PURE__*/React.createElement(StatCard, {
    tone: "brand",
    label: "Ades\xE3o a protocolos",
    value: "96,7",
    unit: "%",
    footnote: "Auditoria set/2026"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.35fr 1fr",
      gap: 20,
      alignItems: "start"
    }
  }, /*#__PURE__*/React.createElement(Card, {
    header: /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center"
      }
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      style: {
        fontFamily: "var(--font-ui)",
        fontSize: 12,
        fontWeight: 600,
        letterSpacing: ".14em",
        textTransform: "uppercase",
        color: "var(--text-tertiary)"
      }
    }, "Ocupa\xE7\xE3o por m\xEAs"), /*#__PURE__*/React.createElement("h4", {
      style: {
        fontFamily: "var(--font-display)",
        fontSize: 20,
        fontWeight: 700,
        color: "var(--text-primary)",
        margin: "4px 0 0"
      }
    }, "M\xE9dia consolidada")), /*#__PURE__*/React.createElement(Tabs, {
      variant: "pill",
      value: range,
      onChange: setRange,
      items: ["Semana", "Mês", "Ano"]
    }))
  }, /*#__PURE__*/React.createElement(BarChart, {
    height: 200,
    showValues: true,
    color: "var(--navy-700)",
    data: [{
      label: "Abr",
      value: 78
    }, {
      label: "Mai",
      value: 84
    }, {
      label: "Jun",
      value: 81
    }, {
      label: "Jul",
      value: 89
    }, {
      label: "Ago",
      value: 92
    }, {
      label: "Set",
      value: 88
    }]
  })), /*#__PURE__*/React.createElement(Card, {
    header: /*#__PURE__*/React.createElement("h4", {
      style: {
        fontFamily: "var(--font-display)",
        fontSize: 18,
        fontWeight: 700,
        color: "var(--text-primary)",
        margin: 0
      }
    }, "Ocupa\xE7\xE3o por ala")
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(ProgressBar, {
    label: "Ala Norte",
    value: 92,
    showValue: true,
    tone: "warning"
  }), /*#__PURE__*/React.createElement(ProgressBar, {
    label: "Ala Sul",
    value: 64,
    showValue: true
  }), /*#__PURE__*/React.createElement(ProgressBar, {
    label: "Ala Leste",
    value: 78,
    showValue: true,
    tone: "accent"
  }), /*#__PURE__*/React.createElement(ProgressBar, {
    label: "Centro-dia",
    value: 38,
    showValue: true,
    tone: "success"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 22,
      padding: 14,
      borderRadius: "var(--radius-md)",
      background: "var(--navy-50)",
      display: "flex",
      gap: 11
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      color: "var(--navy-600)"
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: "info",
    size: 17
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-xs)",
      color: "var(--text-body)",
      lineHeight: "var(--leading-normal)"
    }
  }, "Ala Norte acima do limite de seguran\xE7a (90%). Considere redistribuir novas admiss\xF5es.")))), /*#__PURE__*/React.createElement(Card, {
    padding: "sm",
    header: /*#__PURE__*/React.createElement("div", {
      style: {
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        paddingBottom: 4
      }
    }, /*#__PURE__*/React.createElement("h4", {
      style: {
        fontFamily: "var(--font-display)",
        fontSize: 18,
        fontWeight: 700,
        color: "var(--text-primary)",
        margin: 0
      }
    }, "Intercorr\xEAncias do turno"), /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm",
      iconAfter: "arrow-right"
    }, "Ver todas"))
  }, /*#__PURE__*/React.createElement(DataTable, {
    dense: true,
    onRowClick: onOpenPatient,
    columns: [{
      key: "h",
      label: "Hora",
      numeric: true,
      width: 80
    }, {
      key: "r",
      label: "Residente"
    }, {
      key: "l",
      label: "Leito",
      width: 90
    }, {
      key: "e",
      label: "Evento"
    }, {
      key: "s",
      label: "Status",
      align: "right",
      width: 130
    }],
    rows: [{
      h: "14:32",
      r: "Maria S. Andrade",
      l: "N-104",
      e: "Pressão arterial alterada",
      s: /*#__PURE__*/React.createElement(Badge, {
        tone: "warning",
        size: "sm",
        dot: true
      }, "Em observa\xE7\xE3o")
    }, {
      h: "12:05",
      r: "João P. Ferreira",
      l: "N-108",
      e: "Ajuste de prescrição",
      s: /*#__PURE__*/React.createElement(Badge, {
        tone: "success",
        size: "sm",
        dot: true
      }, "Resolvido")
    }, {
      h: "09:48",
      r: "Ana L. Moreira",
      l: "S-201",
      e: "Coleta laboratorial",
      s: /*#__PURE__*/React.createElement(Badge, {
        tone: "info",
        size: "sm",
        dot: true
      }, "Aguardando")
    }, {
      h: "07:20",
      r: "Carlos E. Lima",
      l: "L-312",
      e: "Queda sem lesão",
      s: /*#__PURE__*/React.createElement(Badge, {
        tone: "danger",
        size: "sm",
        dot: true
      }, "Notificado")
    }]
  })));
}
Object.assign(window, {
  Dashboard
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/sistema/Dashboard.jsx", error: String((e && e.message) || e) }); }

// ui_kits/sistema/PatientDetail.jsx
try { (() => {
const {
  Card,
  Badge,
  Button,
  Tabs,
  Breadcrumbs,
  StatCard,
  ProgressBar,
  DataTable,
  Field,
  Textarea,
  Switch,
  Dialog,
  Icon,
  Toast
} = window.OpalusDesignSystem_2ac06f;
function PatientDetail({
  onBack
}) {
  const [tab, setTab] = React.useState("evolucao");
  const [dlg, setDlg] = React.useState(false);
  const [toast, setToast] = React.useState(false);
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: "auto",
      padding: 28,
      display: "flex",
      flexDirection: "column",
      gap: 20,
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement(Breadcrumbs, {
    items: [{
      label: "Residentes",
      href: "#"
    }, {
      label: "Ala Norte",
      href: "#"
    }, {
      label: "Maria S. Andrade"
    }]
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "flex-start",
      gap: 18
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 60,
      height: 60,
      borderRadius: "var(--radius-lg)",
      background: "var(--gradient-symbol)",
      color: "var(--grey-0)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "var(--font-ui)",
      fontSize: 21,
      fontWeight: 600,
      flexShrink: 0
    }
  }, "MA"), /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 28,
      fontWeight: 700,
      letterSpacing: "-.02em",
      color: "var(--text-primary)",
      margin: 0
    }
  }, "Maria S. Andrade"), /*#__PURE__*/React.createElement(Badge, {
    tone: "warning",
    dot: true
  }, "Em observa\xE7\xE3o")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 20,
      marginTop: 7,
      fontSize: "var(--text-xs)",
      color: "var(--text-secondary)",
      fontFamily: "var(--font-ui)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "82 anos"), /*#__PURE__*/React.createElement("span", null, "Leito N-104"), /*#__PURE__*/React.createElement("span", null, "Opalus Premier"), /*#__PURE__*/React.createElement("span", null, "Prontu\xE1rio 44.821"), /*#__PURE__*/React.createElement("span", null, "Admiss\xE3o 14/09/2026"))), /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    size: "sm",
    onClick: onBack,
    icon: "arrow-left"
  }, "Voltar"), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    icon: "pill",
    onClick: () => setDlg(true)
  }, "Nova prescri\xE7\xE3o")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(4,1fr)",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(StatCard, {
    label: "Press\xE3o arterial",
    value: "148/92",
    unit: "mmHg",
    delta: "+8",
    deltaTone: "danger",
    icon: "heart-pulse"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Satura\xE7\xE3o",
    value: "96",
    unit: "%",
    icon: "activity"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Frequ\xEAncia card.",
    value: "82",
    unit: "bpm",
    icon: "heart"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Dias de interna\xE7\xE3o",
    value: "12",
    icon: "calendar-days"
  })), /*#__PURE__*/React.createElement(Tabs, {
    value: tab,
    onChange: setTab,
    items: [{
      id: "evolucao",
      label: "Evolução",
      icon: "notebook-pen",
      count: 34
    }, {
      id: "prescricoes",
      label: "Prescrições",
      icon: "pill",
      count: 6
    }, {
      id: "exames",
      label: "Exames",
      icon: "flask-conical"
    }, {
      id: "plano",
      label: "Plano de cuidado",
      icon: "clipboard-list"
    }]
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.4fr 1fr",
      gap: 20,
      alignItems: "start"
    }
  }, /*#__PURE__*/React.createElement(Card, {
    padding: "sm"
  }, /*#__PURE__*/React.createElement(DataTable, {
    dense: true,
    columns: [{
      key: "d",
      label: "Data",
      numeric: true,
      width: 110
    }, {
      key: "p",
      label: "Profissional"
    }, {
      key: "n",
      label: "Registro"
    }],
    rows: [{
      d: "25/08 14:32",
      p: "R. Costa · Enf.",
      n: "PA alterada, mantida observação e reavaliação em 2h."
    }, {
      d: "25/08 08:10",
      p: "L. Duarte · Méd.",
      n: "Ajuste de anti-hipertensivo conforme protocolo PA-03."
    }, {
      d: "24/08 21:45",
      p: "T. Alves · Téc.",
      n: "Sinais vitais dentro do esperado. Boa aceitação da dieta."
    }, {
      d: "24/08 15:02",
      p: "R. Costa · Enf.",
      n: "Fisioterapia motora realizada, sem intercorrências."
    }]
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement("h4", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 17,
      fontWeight: 700,
      color: "var(--text-primary)",
      margin: "0 0 14px"
    }
  }, "Plano de cuidado"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 13
    }
  }, /*#__PURE__*/React.createElement(ProgressBar, {
    label: "Mobilidade",
    value: 72,
    showValue: true,
    size: "sm"
  }), /*#__PURE__*/React.createElement(ProgressBar, {
    label: "Nutri\xE7\xE3o",
    value: 88,
    showValue: true,
    size: "sm",
    tone: "success"
  }), /*#__PURE__*/React.createElement(ProgressBar, {
    label: "Cogni\xE7\xE3o",
    value: 54,
    showValue: true,
    size: "sm",
    tone: "accent"
  }))), /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement(Field, {
    label: "Novo registro de evolu\xE7\xE3o"
  }, /*#__PURE__*/React.createElement(Textarea, {
    rows: 4,
    placeholder: "Descreva a evolu\xE7\xE3o do turno"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      marginTop: 14
    }
  }, /*#__PURE__*/React.createElement(Switch, {
    label: "Notificar m\xE9dico",
    checked: true,
    onChange: () => {}
  }), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    iconAfter: "check",
    onClick: () => setToast(true)
  }, "Salvar"))))), /*#__PURE__*/React.createElement(Dialog, {
    open: dlg,
    title: "Nova prescri\xE7\xE3o",
    description: "O registro ser\xE1 enviado \xE0 farm\xE1cia ap\xF3s a assinatura eletr\xF4nica.",
    onClose: () => setDlg(false),
    footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "secondary",
      onClick: () => setDlg(false)
    }, "Cancelar"), /*#__PURE__*/React.createElement(Button, {
      onClick: () => {
        setDlg(false);
        setToast(true);
      }
    }, "Assinar e enviar"))
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(Field, {
    label: "Medicamento"
  }, /*#__PURE__*/React.createElement(Textarea, {
    rows: 2,
    placeholder: "Losartana 50mg \u2014 1 comprimido, 12/12h"
  })), /*#__PURE__*/React.createElement(Switch, {
    label: "Prescri\xE7\xE3o de uso cont\xEDnuo",
    checked: true,
    onChange: () => {}
  }))), toast && /*#__PURE__*/React.createElement("div", {
    style: {
      position: "fixed",
      right: 28,
      bottom: 28,
      zIndex: 70
    }
  }, /*#__PURE__*/React.createElement(Toast, {
    tone: "success",
    title: "Registro salvo",
    onClose: () => setToast(false)
  }, "Evolu\xE7\xE3o registrada \xE0s 14:32.")));
}
Object.assign(window, {
  PatientDetail
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/sistema/PatientDetail.jsx", error: String((e && e.message) || e) }); }

// ui_kits/sistema/PatientList.jsx
try { (() => {
const {
  DataTable,
  Badge,
  Tag,
  Button,
  Input,
  Select,
  Card,
  IconButton,
  Tooltip
} = window.OpalusDesignSystem_2ac06f;
const PEOPLE = [["Maria S. Andrade", "N-104", "82", "Premier", "success", "Estável", "12"], ["João P. Ferreira", "N-108", "78", "Premier", "warning", "Atenção", "9"], ["Ana L. Moreira", "S-201", "85", "Pleno", "info", "Exames", "4"], ["Carlos E. Lima", "L-312", "91", "Geriatrics", "danger", "Crítico", "21"], ["Beatriz N. Rocha", "S-118", "74", "Pleno", "success", "Estável", "6"], ["Otávio M. Prado", "N-121", "88", "Premier", "success", "Estável", "31"]];
function PatientList({
  onOpen
}) {
  const [filter, setFilter] = React.useState("Todos");
  const rows = PEOPLE.filter(p => filter === "Todos" || p[3] === filter).map((p, i) => ({
    id: i,
    nome: /*#__PURE__*/React.createElement("span", {
      style: {
        fontWeight: 600,
        color: "var(--text-primary)"
      }
    }, p[0]),
    leito: p[1],
    idade: p[2],
    unidade: /*#__PURE__*/React.createElement(Tag, null, p[3]),
    status: /*#__PURE__*/React.createElement(Badge, {
      tone: p[4],
      size: "sm",
      dot: true
    }, p[5]),
    dias: p[6],
    acoes: /*#__PURE__*/React.createElement("span", {
      style: {
        display: "inline-flex",
        gap: 4,
        justifyContent: "flex-end"
      }
    }, /*#__PURE__*/React.createElement(Tooltip, {
      label: "Prontu\xE1rio"
    }, /*#__PURE__*/React.createElement(IconButton, {
      icon: "file-text",
      label: "Prontu\xE1rio",
      size: "sm"
    })), /*#__PURE__*/React.createElement(Tooltip, {
      label: "Prescrever"
    }, /*#__PURE__*/React.createElement(IconButton, {
      icon: "pill",
      label: "Prescrever",
      size: "sm"
    })))
  }));
  return /*#__PURE__*/React.createElement("div", {
    style: {
      flex: 1,
      overflow: "auto",
      padding: 28,
      display: "flex",
      flexDirection: "column",
      gap: 18
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 12
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      flex: 1
    }
  }, ["Todos", "Premier", "Pleno", "Geriatrics"].map(f => /*#__PURE__*/React.createElement(Tag, {
    key: f,
    selected: filter === f,
    onClick: () => setFilter(f)
  }, f))), /*#__PURE__*/React.createElement("div", {
    style: {
      width: 170
    }
  }, /*#__PURE__*/React.createElement(Select, {
    size: "sm",
    placeholder: "Ordenar por",
    options: ["Nome", "Leito", "Dias de internação"]
  })), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    variant: "secondary",
    icon: "download"
  }, "Exportar"), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    icon: "user-plus"
  }, "Nova admiss\xE3o")), /*#__PURE__*/React.createElement(DataTable, {
    onRowClick: onOpen,
    columns: [{
      key: "nome",
      label: "Residente"
    }, {
      key: "leito",
      label: "Leito",
      width: 90
    }, {
      key: "idade",
      label: "Idade",
      numeric: true,
      width: 80,
      align: "right"
    }, {
      key: "unidade",
      label: "Unidade",
      width: 130
    }, {
      key: "status",
      label: "Status",
      width: 150
    }, {
      key: "dias",
      label: "Dias",
      numeric: true,
      align: "right",
      width: 80,
      sorted: "desc"
    }, {
      key: "acoes",
      label: "",
      align: "right",
      width: 90
    }],
    rows: rows
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      fontSize: "var(--text-xs)",
      color: "var(--text-tertiary)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "Exibindo ", rows.length, " de 1.284 residentes"), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 6
    }
  }, /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    variant: "secondary",
    icon: "chevron-left"
  }, "Anterior"), /*#__PURE__*/React.createElement(Button, {
    size: "sm",
    variant: "secondary",
    iconAfter: "chevron-right"
  }, "Pr\xF3xima"))));
}
Object.assign(window, {
  PatientList
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/sistema/PatientList.jsx", error: String((e && e.message) || e) }); }

// ui_kits/site/ContactPage.jsx
try { (() => {
const {
  Button,
  Card,
  Field,
  Input,
  Textarea,
  Select,
  Checkbox,
  Alert,
  Icon
} = window.OpalusDesignSystem_2ac06f;
function ContactPage() {
  const [sent, setSent] = React.useState(false);
  return /*#__PURE__*/React.createElement(Section, {
    tone: "page",
    py: 72
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 64,
      alignItems: "start"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Eyebrow, null, "Atendimento"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 40,
      fontWeight: 800,
      letterSpacing: "-.03em",
      color: "var(--text-primary)",
      margin: 0
    }
  }, "Fale com a nossa equipe"), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 14,
      fontSize: 18,
      fontWeight: 300,
      color: "var(--text-secondary)",
      maxWidth: 440
    }
  }, "Conte um pouco sobre a necessidade de cuidado. Respondemos em at\xE9 um dia \xFAtil."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 14,
      marginTop: 34
    }
  }, [["phone", "0800 000 0000", "Central de atendimento, 8h às 20h"], ["mail", "contato@opalus.com.br", "Comercial e institucional"], ["map-pin", "Av. Brigadeiro Faria Lima, 000", "São Paulo · SP"]].map(([i, a, b]) => /*#__PURE__*/React.createElement("div", {
    key: a,
    style: {
      display: "flex",
      gap: 14,
      alignItems: "flex-start"
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 38,
      height: 38,
      borderRadius: "var(--radius-md)",
      background: "var(--navy-50)",
      color: "var(--navy-700)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: i,
    size: 18
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-md)",
      fontWeight: 600,
      color: "var(--text-primary)"
    }
  }, a), /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: "var(--text-sm)",
      color: "var(--text-tertiary)"
    }
  }, b))))), /*#__PURE__*/React.createElement("img", {
    src: "../../assets/illustrations/flow-streams.svg",
    alt: "",
    style: {
      width: "100%",
      marginTop: 40,
      opacity: .9
    }
  })), /*#__PURE__*/React.createElement(Card, {
    padding: "lg"
  }, sent && /*#__PURE__*/React.createElement(Alert, {
    tone: "success",
    title: "Mensagem enviada",
    style: {
      marginBottom: 20
    }
  }, "Nossa equipe responde em at\xE9 um dia \xFAtil."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gap: 18
    }
  }, /*#__PURE__*/React.createElement(Field, {
    label: "Nome completo",
    required: true
  }, /*#__PURE__*/React.createElement(Input, {
    placeholder: "Como podemos chamar voc\xEA?"
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 16
    }
  }, /*#__PURE__*/React.createElement(Field, {
    label: "E-mail",
    required: true
  }, /*#__PURE__*/React.createElement(Input, {
    type: "email",
    placeholder: "voce@email.com",
    icon: "mail"
  })), /*#__PURE__*/React.createElement(Field, {
    label: "Telefone"
  }, /*#__PURE__*/React.createElement(Input, {
    placeholder: "(00) 00000-0000",
    icon: "phone"
  }))), /*#__PURE__*/React.createElement(Field, {
    label: "Unidade de interesse"
  }, /*#__PURE__*/React.createElement(Select, {
    placeholder: "Selecione a unidade",
    options: ["Opalus Premier", "Opalus Pleno", "Opalus Geriatrics", "Ainda não sei"]
  })), /*#__PURE__*/React.createElement(Field, {
    label: "Como podemos ajudar?"
  }, /*#__PURE__*/React.createElement(Textarea, {
    rows: 4,
    placeholder: "Descreva brevemente a necessidade de cuidado"
  })), /*#__PURE__*/React.createElement(Checkbox, {
    label: "Autorizo o contato por telefone e e-mail",
    checked: true,
    onChange: () => {}
  }), /*#__PURE__*/React.createElement(Button, {
    size: "lg",
    fullWidth: true,
    iconAfter: "send",
    onClick: () => setSent(true)
  }, "Enviar mensagem")))));
}
Object.assign(window, {
  ContactPage
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/site/ContactPage.jsx", error: String((e && e.message) || e) }); }

// ui_kits/site/HomePage.jsx
try { (() => {
const {
  Button,
  Icon,
  Badge,
  Card,
  StatCard,
  ProgressBar
} = window.OpalusDesignSystem_2ac06f;
function Hero() {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: "var(--gradient-navy)",
      color: "var(--text-inverse)",
      padding: "96px 32px 104px",
      position: "relative",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/illustrations/node-mesh.svg",
    alt: "",
    style: {
      position: "absolute",
      right: -80,
      top: -40,
      width: 620,
      opacity: .2
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      position: "relative",
      display: "grid",
      gridTemplateColumns: "1.15fr .85fr",
      gap: 64,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-ui)",
      fontSize: 12,
      fontWeight: 600,
      letterSpacing: ".14em",
      textTransform: "uppercase",
      color: "var(--navy-300)",
      marginBottom: 18
    }
  }, "Grupo Opalus \xB7 desde 2008"), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 60,
      fontWeight: 900,
      lineHeight: 1.02,
      letterSpacing: "-.03em",
      color: "var(--grey-0)",
      margin: 0
    }
  }, "Cuidado de longa", /*#__PURE__*/React.createElement("br", null), "perman\xEAncia com", /*#__PURE__*/React.createElement("br", null), "t\xE9cnica e humanidade."), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 24,
      fontSize: 20,
      fontWeight: 300,
      lineHeight: 1.5,
      color: "var(--text-inverse-muted)",
      maxWidth: 520
    }
  }, "Quatro unidades, uma \xFAnica forma de cuidar: protocolos assistenciais rigorosos, equipe multiprofissional e acompanhamento cont\xEDnuo da fam\xEDlia."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 12,
      marginTop: 36
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "inverse",
    size: "lg",
    iconAfter: "arrow-right"
  }, "Agendar uma visita"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    size: "lg",
    style: {
      color: "var(--grey-0)",
      border: "1px solid rgba(255,255,255,.28)"
    }
  }, "Conhe\xE7a as unidades"))), /*#__PURE__*/React.createElement("img", {
    src: "../../assets/illustrations/orbit-core.svg",
    alt: "",
    style: {
      width: "100%"
    }
  })));
}
function Pillars() {
  const items = [{
    i: "shield-check",
    t: "Excelência",
    d: "Protocolos auditados e indicadores assistenciais publicados mensalmente."
  }, {
    i: "heart-handshake",
    t: "Humanização",
    d: "Plano de cuidado individual, construído com o residente e a família."
  }, {
    i: "scale",
    t: "Ética",
    d: "Governança clínica independente e transparência em todas as decisões."
  }, {
    i: "stethoscope",
    t: "Técnica profissional",
    d: "Equipe multiprofissional própria, com educação continuada."
  }];
  return /*#__PURE__*/React.createElement(Section, {
    tone: "page"
  }, /*#__PURE__*/React.createElement(Eyebrow, null, "Nossos valores"), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 38,
      fontWeight: 700,
      letterSpacing: "-.015em",
      color: "var(--text-primary)",
      margin: 0,
      maxWidth: 620
    }
  }, "Seis princ\xEDpios sustentam cada decis\xE3o assistencial."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(4,1fr)",
      gap: 20,
      marginTop: 44
    }
  }, items.map(x => /*#__PURE__*/React.createElement(Card, {
    key: x.t,
    interactive: true
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      width: 44,
      height: 44,
      borderRadius: "var(--radius-md)",
      background: "var(--navy-50)",
      color: "var(--navy-700)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement(Icon, {
    name: x.i,
    size: 22
  })), /*#__PURE__*/React.createElement("h4", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 20,
      fontWeight: 700,
      color: "var(--text-primary)",
      margin: "0 0 8px"
    }
  }, x.t), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: "var(--text-sm)",
      lineHeight: "var(--leading-relaxed)",
      color: "var(--text-secondary)"
    }
  }, x.d)))));
}
function Indicators() {
  return /*#__PURE__*/React.createElement(Section, {
    tone: "tint"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: ".9fr 1.1fr",
      gap: 64,
      alignItems: "center"
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Eyebrow, null, "Indicadores abertos"), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 34,
      fontWeight: 700,
      letterSpacing: "-.015em",
      color: "var(--text-primary)",
      margin: 0
    }
  }, "O que medimos, publicamos."), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 16,
      fontSize: "var(--text-md)",
      lineHeight: "var(--leading-relaxed)",
      color: "var(--text-secondary)",
      maxWidth: 420
    }
  }, "Pain\xE9is de qualidade atualizados mensalmente e auditados por nossa governan\xE7a cl\xEDnica."), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 26
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "secondary",
    iconAfter: "arrow-up-right"
  }, "Ver painel completo"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1fr 1fr",
      gap: 14
    }
  }, /*#__PURE__*/React.createElement(StatCard, {
    label: "Satisfa\xE7\xE3o das fam\xEDlias",
    value: "96,7",
    unit: "%",
    delta: "+2,1 p.p.",
    icon: "smile",
    footnote: "NPS trimestral"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Ades\xE3o a protocolos",
    value: "98,2",
    unit: "%",
    icon: "clipboard-check",
    footnote: "Auditoria set/2026"
  }), /*#__PURE__*/React.createElement(StatCard, {
    label: "Leitos ativos",
    value: "1.284",
    icon: "bed-double",
    footnote: "4 unidades"
  }), /*#__PURE__*/React.createElement(StatCard, {
    tone: "brand",
    label: "Equipe pr\xF3pria",
    value: "620",
    unit: "profissionais"
  }))));
}
function Units({
  onOpen
}) {
  const units = [{
    n: "Opalus Premier",
    d: "Residência sênior de alta complexidade",
    c: "var(--blue-600)",
    i: "data-constellation"
  }, {
    n: "Opalus Pleno",
    d: "Cuidado assistido e centro-dia",
    c: "var(--teal-500)",
    i: "signal-bars"
  }, {
    n: "Opalus Geriatrics",
    d: "Ambulatório e reabilitação geriátrica",
    c: "var(--purple-500)",
    i: "pulse-trace"
  }];
  return /*#__PURE__*/React.createElement(Section, {
    tone: "page"
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "flex-end",
      marginBottom: 40
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Eyebrow, null, "Controladas"), /*#__PURE__*/React.createElement("h2", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 34,
      fontWeight: 700,
      letterSpacing: "-.015em",
      color: "var(--text-primary)",
      margin: 0
    }
  }, "Tr\xEAs marcas, um mesmo padr\xE3o.")), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    iconAfter: "arrow-right",
    onClick: onOpen
  }, "Todas as unidades")), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(3,1fr)",
      gap: 20
    }
  }, units.map(u => /*#__PURE__*/React.createElement(Card, {
    key: u.n,
    interactive: true,
    padding: "sm",
    onClick: onOpen
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      borderRadius: "var(--radius-md)",
      background: "var(--navy-50)",
      padding: 12,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: `../../assets/illustrations/${u.i}.svg`,
    alt: "",
    style: {
      width: "100%",
      display: "block"
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      alignItems: "center",
      gap: 10,
      marginBottom: 6
    }
  }, /*#__PURE__*/React.createElement("span", {
    style: {
      width: 8,
      height: 8,
      borderRadius: 999,
      background: u.c
    }
  }), /*#__PURE__*/React.createElement("h4", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 19,
      fontWeight: 700,
      color: "var(--text-primary)",
      margin: 0
    }
  }, u.n)), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: "var(--text-sm)",
      color: "var(--text-secondary)"
    }
  }, u.d)))));
}
function CtaBand() {
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: "var(--gradient-blue)",
      color: "var(--text-inverse)",
      padding: "72px 32px",
      position: "relative",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/illustrations/cross-lattice.svg",
    alt: "",
    style: {
      position: "absolute",
      left: -40,
      bottom: -60,
      width: 460,
      opacity: .2
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      position: "relative",
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      gap: 40
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 30,
      fontWeight: 700,
      letterSpacing: "-.015em",
      color: "var(--grey-0)",
      margin: 0
    }
  }, "Vamos conversar sobre o cuidado que sua fam\xEDlia precisa."), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: "10px 0 0",
      color: "var(--text-inverse-muted)",
      fontSize: "var(--text-md)"
    }
  }, "Nossa equipe responde em at\xE9 um dia \xFAtil.")), /*#__PURE__*/React.createElement(Button, {
    variant: "inverse",
    size: "lg",
    icon: "phone"
  }, "Falar com a equipe")));
}
function HomePage({
  onOpenUnits
}) {
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Hero, null), /*#__PURE__*/React.createElement(Pillars, null), /*#__PURE__*/React.createElement(Indicators, null), /*#__PURE__*/React.createElement(Units, {
    onOpen: onOpenUnits
  }), /*#__PURE__*/React.createElement(CtaBand, null));
}
Object.assign(window, {
  HomePage,
  Hero,
  Pillars,
  Indicators,
  Units,
  CtaBand
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/site/HomePage.jsx", error: String((e && e.message) || e) }); }

// ui_kits/site/Shared.jsx
try { (() => {
const {
  Button,
  Icon,
  Logo,
  Badge,
  Card,
  StatCard,
  TopBar
} = window.OpalusDesignSystem_2ac06f;
function Section({
  children,
  tone = "page",
  py = 96,
  style
}) {
  const bg = {
    page: "var(--grey-0)",
    tint: "var(--navy-50)",
    brand: "var(--gradient-navy)",
    sunken: "var(--surface-sunken)"
  }[tone];
  return /*#__PURE__*/React.createElement("section", {
    style: {
      background: bg,
      color: tone === "brand" ? "var(--text-inverse)" : "var(--text-body)",
      padding: `${py}px 32px`,
      ...style
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto"
    }
  }, children));
}
function Eyebrow({
  children,
  tone = "var(--teal-500)"
}) {
  return /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-ui)",
      fontSize: 12,
      fontWeight: 600,
      letterSpacing: ".14em",
      textTransform: "uppercase",
      color: tone,
      marginBottom: 14
    }
  }, children);
}
function SiteFooter() {
  const cols = [{
    h: "Institucional",
    l: ["Quem somos", "Governança", "Trabalhe conosco"]
  }, {
    h: "Unidades",
    l: ["Opalus Premier", "Opalus Pleno", "Opalus Geriatrics"]
  }, {
    h: "Atendimento",
    l: ["Central 0800", "Fale com a equipe", "Portal do cliente"]
  }];
  return /*#__PURE__*/React.createElement("footer", {
    style: {
      background: "var(--navy-800)",
      color: "var(--text-inverse-muted)",
      padding: "64px 32px 32px",
      position: "relative",
      overflow: "hidden"
    }
  }, /*#__PURE__*/React.createElement("img", {
    src: "../../assets/symbol-white.png",
    alt: "",
    style: {
      position: "absolute",
      right: -60,
      bottom: -90,
      width: 300,
      opacity: .07
    }
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto",
      position: "relative"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "1.4fr repeat(3,1fr)",
      gap: 48
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Logo, {
    tone: "white",
    height: 30,
    base: "../../assets"
  }), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 18,
      fontSize: "var(--text-sm)",
      maxWidth: 280,
      lineHeight: "var(--leading-relaxed)"
    }
  }, "Excel\xEAncia, humaniza\xE7\xE3o e t\xE9cnica profissional no cuidado de longa perman\xEAncia.")), cols.map(c => /*#__PURE__*/React.createElement("div", {
    key: c.h
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: "var(--font-ui)",
      fontSize: 12,
      fontWeight: 600,
      letterSpacing: ".14em",
      textTransform: "uppercase",
      color: "rgba(255,255,255,.45)",
      marginBottom: 14
    }
  }, c.h), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      flexDirection: "column",
      gap: 9
    }
  }, c.l.map(x => /*#__PURE__*/React.createElement("a", {
    key: x,
    href: "#",
    style: {
      fontSize: "var(--text-sm)",
      color: "var(--text-inverse-muted)",
      textDecoration: "none"
    }
  }, x)))))), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 56,
      paddingTop: 22,
      borderTop: "1px solid rgba(255,255,255,.12)",
      display: "flex",
      justifyContent: "space-between",
      fontSize: "var(--text-2xs)",
      color: "rgba(255,255,255,.5)"
    }
  }, /*#__PURE__*/React.createElement("span", null, "\xA9 2026 Grupo Opalus. Todos os direitos reservados."), /*#__PURE__*/React.createElement("span", {
    style: {
      display: "flex",
      gap: 22
    }
  }, /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      color: "inherit",
      textDecoration: "none"
    }
  }, "Privacidade"), /*#__PURE__*/React.createElement("a", {
    href: "#",
    style: {
      color: "inherit",
      textDecoration: "none"
    }
  }, "Termos")))));
}
Object.assign(window, {
  Section,
  Eyebrow,
  SiteFooter
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/site/Shared.jsx", error: String((e && e.message) || e) }); }

// ui_kits/site/UnitsPage.jsx
try { (() => {
const {
  Button,
  Icon,
  Badge,
  Card,
  Tag,
  DataTable,
  ProgressBar,
  Breadcrumbs,
  Tabs
} = window.OpalusDesignSystem_2ac06f;
function UnitsPage() {
  const [filter, setFilter] = React.useState("Todas");
  const [tab, setTab] = React.useState("estrutura");
  const rows = [{
    id: 1,
    u: "Opalus Premier",
    c: "São Paulo · SP",
    l: "480",
    m: /*#__PURE__*/React.createElement(Badge, {
      tone: "success",
      size: "sm",
      dot: true
    }, "Vagas")
  }, {
    id: 2,
    u: "Opalus Pleno",
    c: "Campinas · SP",
    l: "360",
    m: /*#__PURE__*/React.createElement(Badge, {
      tone: "warning",
      size: "sm",
      dot: true
    }, "Lista de espera")
  }, {
    id: 3,
    u: "Opalus Geriatrics",
    c: "Curitiba · PR",
    l: "264",
    m: /*#__PURE__*/React.createElement(Badge, {
      tone: "success",
      size: "sm",
      dot: true
    }, "Vagas")
  }, {
    id: 4,
    u: "Opalus Pleno",
    c: "Belo Horizonte · MG",
    l: "180",
    m: /*#__PURE__*/React.createElement(Badge, {
      tone: "info",
      size: "sm",
      dot: true
    }, "Em obras")
  }];
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("section", {
    style: {
      background: "var(--navy-50)",
      padding: "40px 32px 56px"
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      maxWidth: "var(--container-max)",
      margin: "0 auto"
    }
  }, /*#__PURE__*/React.createElement(Breadcrumbs, {
    items: [{
      label: "Institucional",
      href: "#"
    }, {
      label: "Unidades"
    }]
  }), /*#__PURE__*/React.createElement("h1", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 44,
      fontWeight: 800,
      letterSpacing: "-.03em",
      color: "var(--text-primary)",
      margin: "18px 0 0"
    }
  }, "Unidades do grupo"), /*#__PURE__*/React.createElement("p", {
    style: {
      marginTop: 12,
      fontSize: 18,
      fontWeight: 300,
      color: "var(--text-secondary)",
      maxWidth: 560
    }
  }, "Quatro endere\xE7os, o mesmo padr\xE3o assistencial. Filtre por regi\xE3o ou modalidade de cuidado."), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "flex",
      gap: 8,
      marginTop: 26
    }
  }, ["Todas", "São Paulo", "Sul", "Sudeste"].map(f => /*#__PURE__*/React.createElement(Tag, {
    key: f,
    selected: filter === f,
    onClick: () => setFilter(f)
  }, f))))), /*#__PURE__*/React.createElement(Section, {
    tone: "page",
    py: 64
  }, /*#__PURE__*/React.createElement(DataTable, {
    columns: [{
      key: "u",
      label: "Unidade"
    }, {
      key: "c",
      label: "Cidade"
    }, {
      key: "l",
      label: "Leitos",
      numeric: true,
      align: "right"
    }, {
      key: "m",
      label: "Disponibilidade",
      align: "right"
    }],
    rows: rows
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 56
    }
  }, /*#__PURE__*/React.createElement(Tabs, {
    value: tab,
    onChange: setTab,
    items: [{
      id: "estrutura",
      label: "Estrutura",
      icon: "building-2"
    }, {
      id: "equipe",
      label: "Equipe",
      icon: "users"
    }, {
      id: "protocolos",
      label: "Protocolos",
      icon: "clipboard-list"
    }]
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      display: "grid",
      gridTemplateColumns: "repeat(3,1fr)",
      gap: 20,
      marginTop: 28
    }
  }, [["Quartos individuais", "Todos com banheiro adaptado e chamada de enfermagem."], ["Centro de reabilitação", "Fisioterapia, fonoaudiologia e terapia ocupacional no local."], ["Retaguarda clínica 24h", "Equipe médica presencial e convênio de urgência."]].map(([t, d]) => /*#__PURE__*/React.createElement(Card, {
    key: t
  }, /*#__PURE__*/React.createElement("h4", {
    style: {
      fontFamily: "var(--font-display)",
      fontSize: 18,
      fontWeight: 700,
      color: "var(--text-primary)",
      margin: "0 0 8px"
    }
  }, t), /*#__PURE__*/React.createElement("p", {
    style: {
      margin: 0,
      fontSize: "var(--text-sm)",
      color: "var(--text-secondary)",
      lineHeight: "var(--leading-relaxed)"
    }
  }, d)))))));
}
Object.assign(window, {
  UnitsPage
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/site/UnitsPage.jsx", error: String((e && e.message) || e) }); }

__ds_ns.Badge = __ds_scope.Badge;

__ds_ns.Button = __ds_scope.Button;

__ds_ns.Card = __ds_scope.Card;

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.IconButton = __ds_scope.IconButton;

__ds_ns.Logo = __ds_scope.Logo;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.BarChart = __ds_scope.BarChart;

__ds_ns.DataTable = __ds_scope.DataTable;

__ds_ns.ProgressBar = __ds_scope.ProgressBar;

__ds_ns.StatCard = __ds_scope.StatCard;

__ds_ns.Alert = __ds_scope.Alert;

__ds_ns.Dialog = __ds_scope.Dialog;

__ds_ns.Toast = __ds_scope.Toast;

__ds_ns.Tooltip = __ds_scope.Tooltip;

__ds_ns.Checkbox = __ds_scope.Checkbox;

__ds_ns.Field = __ds_scope.Field;

__ds_ns.Input = __ds_scope.Input;

__ds_ns.Radio = __ds_scope.Radio;

__ds_ns.Select = __ds_scope.Select;

__ds_ns.Switch = __ds_scope.Switch;

__ds_ns.Textarea = __ds_scope.Textarea;

__ds_ns.Breadcrumbs = __ds_scope.Breadcrumbs;

__ds_ns.SideNav = __ds_scope.SideNav;

__ds_ns.Tabs = __ds_scope.Tabs;

__ds_ns.TopBar = __ds_scope.TopBar;

})();
