import type { CSSProperties, ChangeEventHandler, ReactNode } from "react";
/** Immediate on/off toggle — commits without a save action. */
export interface SwitchProps {
  label?: ReactNode;
  checked?: boolean;
  disabled?: boolean;
  onChange?: ChangeEventHandler<HTMLInputElement>;
  style?: CSSProperties;
}
export function Switch(props: SwitchProps): JSX.Element;
