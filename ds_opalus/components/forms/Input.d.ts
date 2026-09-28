import type { CSSProperties, InputHTMLAttributes } from "react";
/** Single-line text input. */
export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Lucide icon name rendered inside, leading. */
  icon?: string;
  /** Lucide icon name rendered inside, trailing. */
  iconAfter?: string;
  invalid?: boolean;
  size?: "sm" | "md" | "lg";
  style?: CSSProperties;
}
export function Input(props: InputProps): JSX.Element;
