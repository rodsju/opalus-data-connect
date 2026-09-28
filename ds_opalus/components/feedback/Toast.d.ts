import type { CSSProperties, ReactNode, MouseEventHandler } from "react";
/** Transient floating confirmation. Always navy-800, bottom-right, auto-dismiss ~5s. */
export interface ToastProps {
  title?: string;
  children?: ReactNode;
  tone?: "info" | "success" | "warning" | "danger";
  onClose?: MouseEventHandler<HTMLButtonElement>;
  /** Optional single action, usually a ghost inverse Button. */
  action?: ReactNode;
  style?: CSSProperties;
}
export function Toast(props: ToastProps): JSX.Element;
