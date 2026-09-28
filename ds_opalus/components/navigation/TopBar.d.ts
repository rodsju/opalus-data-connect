import type { CSSProperties, ReactNode } from "react";
export interface TopBarLink { label: string; href?: string }
/**
 * Marketing / portal header.
 */
export interface TopBarProps {
  links?: Array<string | TopBarLink>;
  active?: string;
  onNavigate?: (label: string) => void;
  /** Right-hand slot, usually a Button. */
  action?: ReactNode;
  tone?: "light" | "dark";
  assetBase?: string;
  style?: CSSProperties;
}
export function TopBar(props: TopBarProps): JSX.Element;
