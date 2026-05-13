"use client";

import {
  useRef,
  useState,
  useEffect,
  type ClipboardEvent,
  type KeyboardEvent,
} from "react";
import styles from "./CodeField.module.css";

interface Props {
  length?: number;
  value: string;
  onChange: (v: string) => void;
  onComplete?: (v: string) => void;
  email?: string;
  error?: boolean;
  resendInSeconds?: number; // если > 0, кнопка резенда показывает обратный отсчёт
  onResend?: () => void;
  resendDisabled?: boolean;
}

/**
 * Интерактивное поле для 6-значного кода. Поддерживает:
 *  - ввод по одной цифре с авто-переходом,
 *  - Backspace переходит назад,
 *  - вставку (paste) распарсивает и раскладывает по ячейкам,
 *  - вызывает onComplete, когда длина = max.
 */
export function CodeField({
  length = 6,
  value,
  onChange,
  onComplete,
  email,
  error,
  resendInSeconds = 0,
  onResend,
  resendDisabled,
}: Props) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);
  const [cooldown, setCooldown] = useState(resendInSeconds);

  useEffect(() => setCooldown(resendInSeconds), [resendInSeconds]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setInterval(() => setCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [cooldown]);

  const digits: string[] = Array.from(
    { length },
    (_, i) => value[i] ?? "",
  );

  const focusAt = (i: number) => {
    refs.current[Math.max(0, Math.min(length - 1, i))]?.focus();
  };

  const handleChange = (i: number, raw: string) => {
    const next = raw.replace(/\D/g, "").slice(-1); // только последняя цифра
    if (!next && !digits[i]) return;
    const arr = digits.slice();
    arr[i] = next;
    const joined = arr.join("");
    onChange(joined);
    if (next) focusAt(i + 1);
    if (joined.length === length && !joined.includes("")) {
      onComplete?.(joined);
    }
  };

  const handleKey = (i: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      if (digits[i]) {
        const arr = digits.slice();
        arr[i] = "";
        onChange(arr.join(""));
      } else if (i > 0) {
        const arr = digits.slice();
        arr[i - 1] = "";
        onChange(arr.join(""));
        focusAt(i - 1);
      }
    } else if (e.key === "ArrowLeft") {
      focusAt(i - 1);
    } else if (e.key === "ArrowRight") {
      focusAt(i + 1);
    }
  };

  const handlePaste = (e: ClipboardEvent<HTMLInputElement>) => {
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (!text) return;
    e.preventDefault();
    onChange(text);
    focusAt(text.length >= length ? length - 1 : text.length);
    if (text.length === length) onComplete?.(text);
  };

  // Активная ячейка — первая пустая
  const activeIdx = digits.findIndex((d) => !d);

  return (
    <div className={styles.wrap}>
      <div className={styles.labelRow}>
        <span>code</span>
        <span className={styles.line} />
        {email ? (
          <span className={styles.note}>
            // отправлено на <strong>{email}</strong>
          </span>
        ) : null}
      </div>

      <div className={styles.cells}>
        {digits.map((d, i) => (
          <input
            key={i}
            ref={(el) => {
              refs.current[i] = el;
            }}
            className={`${styles.cell} ${
              error ? styles.error : i === activeIdx ? styles.active : ""
            }`}
            value={d}
            onChange={(e) => handleChange(i, e.target.value)}
            onKeyDown={(e) => handleKey(i, e)}
            onPaste={handlePaste}
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={1}
            aria-label={`Цифра ${i + 1}`}
          />
        ))}
      </div>

      {onResend && (
        <div className={styles.foot}>
          <span>// не пришло? проверьте спам</span>
          {cooldown > 0 ? (
            <span>
              resend in <span style={{ color: "var(--yellow)" }}>
                0:{String(cooldown).padStart(2, "0")}
              </span>
            </span>
          ) : (
            <button
              type="button"
              className={styles.resend}
              onClick={() => {
                onResend();
                setCooldown(60);
              }}
              disabled={resendDisabled}
            >
              отправить заново ↻
            </button>
          )}
        </div>
      )}
    </div>
  );
}
