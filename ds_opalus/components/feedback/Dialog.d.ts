import type { CSSProperties, ReactNode } from "react";
/** Modal for focused decisions and short forms. */
export interface DialogProps {
  open?: boolean;
  title?: string;
  description?: string;
  children?: ReactNode;
  /** Action row, right-aligned. Secondary first, primary last. */
  footer?: ReactNode;
  onClose?: () => void;
  width?: number;
  style?: CSSProperties;
}
export function Dialog(props: DialogProps): JSX.Element | null;
