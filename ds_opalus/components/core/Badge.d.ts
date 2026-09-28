import type { CSSProperties, ReactNode } from "react";
/** Status pill — short, uppercase, one or two words. */
export interface BadgeProps {
  children?: ReactNode;
  tone?: "neutral" | "brand" | "info" | "success" | "warning" | "danger" | "purple";
  /** Lucide icon name. */
  icon?: string;
  /** Show a leading status dot instead of an icon. */
  dot?: boolean;
  size?: "sm" | "md";
  style?: CSSProperties;
}
export function Badge(props: BadgeProps): JSX.Element;
