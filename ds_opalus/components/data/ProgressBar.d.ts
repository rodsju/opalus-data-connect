import type { CSSProperties } from "react";
/** Linear progress / utilisation meter. */
export interface ProgressBarProps {
  value?: number;
  max?: number;
  label?: string;
  /** Shows the rounded percentage on the right of the label row. */
  showValue?: boolean;
  tone?: "brand" | "accent" | "success" | "warning" | "danger";
  size?: "sm" | "md" | "lg";
  style?: CSSProperties;
}
export function ProgressBar(props: ProgressBarProps): JSX.Element;
