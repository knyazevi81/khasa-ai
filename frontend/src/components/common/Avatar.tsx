"use client";

import styles from "./Avatar.module.css";

interface Props {
  email: string;
  size?: number;
  borderColor?: string;
}

/**
 * Инициал из email, в квадратной рамке (как в макете dark.jsx — D.raised
 * фон, border бренд-цвета).
 */
export function Avatar({ email, size = 28, borderColor }: Props) {
  const initial = (email[0] || "?").toUpperCase();
  return (
    <div
      className={styles.av}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.46),
        borderColor: borderColor || "var(--red)",
      }}
    >
      {initial}
    </div>
  );
}
