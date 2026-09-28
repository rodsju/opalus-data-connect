import type { CSSProperties, ReactNode, MouseEventHandler } from "react";
/**
 * Primary action control.
 */
export interface ButtonProps {
  children?: ReactNode;
  /** primary = navy institutional. accent = controladas blue. inverse = for navy backgrounds. */
  variant?: "primary" | "secondary" | "accent" | "ghost" | "danger" | "inverse";
  size?: "sm" | "md" | "lg";
  /** Lucide icon name rendered before the label. */
  icon?: string;
  /** Lucide icon name rendered after the label. */
  iconAfter?: string;
  disabled?: boolean;
  fullWidth?: boolean;
  type?: "button" | "submit" | "reset";
  onClick?: MouseEventHandler<HTMLButtonElement>;
  style?: CSSProperties;
}
export function Button(props: ButtonProps): JSX.Element;
