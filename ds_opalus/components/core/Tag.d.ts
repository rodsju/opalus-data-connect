import type { CSSProperties, ReactNode, MouseEventHandler } from "react";
/** Removable / selectable chip for filters and user-authored labels. */
export interface TagProps {
  children?: ReactNode;
  /** Renders a trailing remove affordance. */
  onRemove?: MouseEventHandler<HTMLButtonElement>;
  /** Filled navy state. */
  selected?: boolean;
  onClick?: MouseEventHandler<HTMLSpanElement>;
  style?: CSSProperties;
}
export function Tag(props: TagProps): JSX.Element;
