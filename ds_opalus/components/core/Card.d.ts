import type { CSSProperties, ReactNode, MouseEventHandler } from "react";
/** Surface container — 14px radius, hairline border, navy-tinted shadow. */
export interface CardProps {
  children?: ReactNode;
  padding?: "sm" | "md" | "lg";
  /** Adds hover lift + pointer. */
  interactive?: boolean;
  tone?: "default" | "sunken" | "brand" | "accent";
  header?: ReactNode;
  footer?: ReactNode;
  onClick?: MouseEventHandler<HTMLDivElement>;
  style?: CSSProperties;
}
export function Card(props: CardProps): JSX.Element;
