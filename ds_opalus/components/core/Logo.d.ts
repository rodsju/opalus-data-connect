import type { CSSProperties } from "react";
/** Renders the supplied Opalus lockups. Never recreate the mark in markup. */
export interface LogoProps {
  lockup?: "horizontal" | "vertical" | "symbol";
  /** color = full degradê. white = over photography or institutional colour. mono = single-colour navy. */
  tone?: "color" | "white" | "mono";
  /** Rendered height in px. Width follows. */
  height?: number;
  /** Path prefix to the assets folder, relative to the host page. Default "assets". */
  base?: string;
  style?: CSSProperties;
}
export function Logo(props: LogoProps): JSX.Element;
