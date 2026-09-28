import type { CSSProperties, ChangeEventHandler, ReactNode } from "react";
/** Multi-select control; 18px navy box with a 3px check. */
export interface CheckboxProps {
  label?: ReactNode;
  checked?: boolean;
  /** Mixed state for a parent row. */
  indeterminate?: boolean;
  disabled?: boolean;
  onChange?: ChangeEventHandler<HTMLInputElement>;
  style?: CSSProperties;
}
export function Checkbox(props: CheckboxProps): JSX.Element;
