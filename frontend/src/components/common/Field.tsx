"use client";

import { useState } from "react";
import styles from "./Field.module.css";

interface Props extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string | null;
  togglePassword?: boolean;
}

/**
 * Терминальное поле ввода: лейбл капсом, > курсор, моноширинный текст.
 * Можно навесить show/hide для пароля.
 */
export function Field({ label, error, togglePassword, type, ...rest }: Props) {
  const [shown, setShown] = useState(false);
  const effectiveType = togglePassword
    ? shown
      ? "text"
      : "password"
    : type;

  return (
    <label className={styles.field}>
      <span className={styles.label}>{label}</span>
      <div className={styles.box}>
        <span className={styles.prompt}>&gt;</span>
        <input className={styles.input} type={effectiveType} {...rest} />
        {togglePassword && (
          <button
            type="button"
            className={styles.suffix}
            onClick={() => setShown((v) => !v)}
            tabIndex={-1}
          >
            {shown ? "HIDE" : "SHOW"}
          </button>
        )}
      </div>
      {error && (
        <div className={styles.error}>
          <span style={{ fontWeight: 700 }}>!</span>
          <span>{error}</span>
        </div>
      )}
    </label>
  );
}
