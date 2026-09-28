import type { CSSProperties, SelectHTMLAttributes } from "react";
export interface SelectOption { value: string; label: string }
/** Native select with Opalus chrome. */
export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "children"> {
  options?: Array<string | SelectOption>;
  placeholder?: string;
  invalid?: boolean;
  size?: "sm" | "md" | "lg";
  style?: CSSProperties;
}
export function Select(props: SelectProps): JSX.Element;
