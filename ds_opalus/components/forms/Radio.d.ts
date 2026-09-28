import type { CSSProperties, ChangeEventHandler, ReactNode } from "react";
/** Single-choice control. Group by shared `name`. */
export interface RadioProps {
  label?: ReactNode;
  checked?: boolean;
  disabled?: boolean;
  name?: string;
  value?: string;
  onChange?: ChangeEventHandler<HTMLInputElement>;
  style?: CSSProperties;
}
export function Radio(props: RadioProps): JSX.Element;
