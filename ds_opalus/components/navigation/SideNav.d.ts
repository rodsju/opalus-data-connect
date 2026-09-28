import type { CSSProperties, ReactNode } from "react";
export interface SideNavItem { id?: string; label?: string; icon?: string; count?: number; section?: string }
/** Navy application sidebar with the white lockup at the top. */
export interface SideNavProps {
  /** Mix nav items and `{ section: "Label" }` separators. */
  items?: SideNavItem[];
  value?: string;
  onChange?: (id: string) => void;
  footer?: ReactNode;
  /** Relative path to the assets folder for the logo. */
  assetBase?: string;
  width?: number;
  style?: CSSProperties;
}
export function SideNav(props: SideNavProps): JSX.Element;
