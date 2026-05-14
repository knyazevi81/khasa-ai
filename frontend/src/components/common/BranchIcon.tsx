interface Props {
  size?: number;
  color?: string;
}

/**
 * Иконка ветвления — две точки слева, одна справа, связанные «вилкой».
 * Скопирована из `khasa-dark.jsx` (там же используется в топбарах).
 */
export function BranchIcon({ size = 14, color = "currentColor" }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke={color}
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="3" cy="3" r="1.6" />
      <circle cx="3" cy="13" r="1.6" />
      <circle cx="13" cy="8" r="1.6" />
      <path d="M3 4.6 V 11.4" />
      <path d="M4.4 3 H 9 a 2.5 2.5 0 0 1 2.5 2.5 V 6.5" />
      <path d="M4.4 13 H 9 a 2.5 2.5 0 0 0 2.5 -2.5 V 9.5" />
    </svg>
  );
}
