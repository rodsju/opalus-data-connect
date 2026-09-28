import type { CSSProperties, ReactNode } from "react";
export interface DataColumn {
  key: string;
  label: string;
  align?: "left" | "right" | "center";
  width?: number | string;
  /** Renders the cell in Barlow with tabular figures. */
  numeric?: boolean;
  sorted?: "asc" | "desc";
}
/**
 * Record table for system views.
 */
export interface DataTableProps {
  columns?: DataColumn[];
  /** Cell values may be any node — pass a Badge or Tag for status columns. */
  rows?: Array<Record<string, ReactNode> & { id?: string | number }>;
  dense?: boolean;
  onRowClick?: (row: Record<string, ReactNode>) => void;
  style?: CSSProperties;
}
export function DataTable(props: DataTableProps): JSX.Element;
