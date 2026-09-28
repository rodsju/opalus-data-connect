import type { CSSProperties, MouseEventHandler } from "react";
/** Square icon-only control for toolbars and table rows. */
export interface IconButtonProps {
  /** Lucide icon name. */
  icon: string;
  /** Accessible label — required, the button has no text. */
  label: string;
  variant?: "ghost" | "outline" | "solid" | "inverse";
  size?: "sm" | "md" | "lg";
  disabled?: boolean;
  /** Sticky pressed look for toggles. */
  active?: boolean;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  style?: CSSProperties;
}
export function IconButton(props: IconButtonProps): JSX.Element;
