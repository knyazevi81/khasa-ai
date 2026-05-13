import styles from "./Button.module.css";

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "green" | "yellow" | "red" | "ghost";
  loading?: boolean;
  iconRight?: React.ReactNode;
}

const variantClass = {
  green: "",
  yellow: styles.yellow,
  red: styles.red,
  ghost: styles.ghost,
} as const;

export function Button({
  variant = "green",
  loading,
  iconRight,
  children,
  disabled,
  className,
  ...rest
}: Props) {
  return (
    <button
      className={`${styles.btn} ${variantClass[variant]} ${className ?? ""}`}
      disabled={disabled || loading}
      {...rest}
    >
      <span>{children}</span>
      {loading ? (
        <span className={styles.spinner} aria-hidden>
          <span />
          <span />
          <span />
        </span>
      ) : iconRight ? (
        <span className={styles.iconRight}>{iconRight}</span>
      ) : null}
    </button>
  );
}
