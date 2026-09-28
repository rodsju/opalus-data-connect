import type { CSSProperties, ReactNode } from "react";
/** Label + hint/error wrapper for any form control. */
export interface FieldProps {
  label?: string;
  hint?: string;
  /** When set, replaces the hint and turns it red. */
  error?: string;
  required?: boolean;
  htmlFor?: string;
  children?: ReactNode;
  style?: CSSProperties;
}
export function Field(props: FieldProps): JSX.Element;
