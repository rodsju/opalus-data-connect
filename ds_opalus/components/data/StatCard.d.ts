import type { CSSProperties } from "react";
/**
 * Single KPI tile — Barlow tabular figures at 38px.
 */
export interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  /** Signed string, e.g. "+4,2%". Sign picks the default tone and arrow. */
  delta?: string;
  deltaTone?: "success" | "danger" | "neutral";
  /** Lucide icon name beside the label. */
  icon?: string;
  footnote?: string;
  tone?: "default" | "brand";
  style?: CSSProperties;
}
export function StatCard(props: StatCardProps): JSX.Element;
