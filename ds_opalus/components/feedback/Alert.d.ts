import type { CSSProperties, ReactNode, MouseEventHandler } from "react";
/** Inline, in-flow message tied to a region of the page. */
export interface AlertProps {
  title?: string;
  children?: ReactNode;
  tone?: "info" | "success" | "warning" | "danger";
  /** Override the default Lucide glyph. */
  icon?: string;
  onClose?: MouseEventHandler<HTMLButtonElement>;
  style?: CSSProperties;
}
export function Alert(props: AlertProps): JSX.Element;
