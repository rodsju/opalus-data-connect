import type { CSSProperties } from "react";
export interface Crumb { label: string; href?: string }
/** Ancestor trail; last item is the current page and is not a link. */
export interface BreadcrumbsProps {
  items?: Array<string | Crumb>;
  style?: CSSProperties;
}
export function Breadcrumbs(props: BreadcrumbsProps): JSX.Element;
