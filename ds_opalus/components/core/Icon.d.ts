import type { CSSProperties } from "react";
/** Renders a Lucide glyph at brand stroke weight. Requires the Lucide UMD script on the page. */
export interface IconProps {
  /** Lucide icon name, kebab or Pascal case, e.g. "activity" or "Activity". */
  name: string;
  /** Pixel box. Default 20. */
  size?: number;
  /** Default 1.75 — the Opalus stroke weight. */
  strokeWidth?: number;
  color?: string;
  style?: CSSProperties;
}
export function Icon(props: IconProps): JSX.Element;
