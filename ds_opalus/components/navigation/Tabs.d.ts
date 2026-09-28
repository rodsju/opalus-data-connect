import type { CSSProperties } from "react";
export interface TabItem { id: string; label: string; icon?: string; count?: number }
/** Horizontal view switcher. */
export interface TabsProps {
  items?: Array<string | TabItem>;
  value?: string;
  onChange?: (id: string) => void;
  /** underline = page-level sections. pill = compact in-panel toggle. */
  variant?: "underline" | "pill";
  style?: CSSProperties;
}
export function Tabs(props: TabsProps): JSX.Element;
