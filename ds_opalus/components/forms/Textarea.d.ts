import type { CSSProperties, TextareaHTMLAttributes } from "react";
/** Multi-line text input for notes and observations. */
export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
  rows?: number;
  style?: CSSProperties;
}
export function Textarea(props: TextareaProps): JSX.Element;
