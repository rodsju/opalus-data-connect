import type { CSSProperties, ReactNode } from "react";
/** Hover/focus label for icon-only controls and truncated values. */
export interface TooltipProps {
  /** Short — a few words, no punctuation. */
  label: string;
  children?: ReactNode;
  placement?: "top" | "bottom" | "left" | "right";
  style?: CSSProperties;
}
export function Tooltip(props: TooltipProps): JSX.Element;
