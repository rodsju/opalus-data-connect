import type { CSSProperties } from "react";
export interface BarDatum { label: string; value: number; color?: string }
/** Minimal categorical bar chart using the --chart-* sequence. */
export interface BarChartProps {
  data?: BarDatum[];
  height?: number;
  /** Single colour for all bars; omit to cycle the chart sequence. */
  color?: string;
  showValues?: boolean;
  style?: CSSProperties;
}
export function BarChart(props: BarChartProps): JSX.Element;
