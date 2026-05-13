"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell, Note } from "@/components/auth/AuthShell";
import { Field } from "@/components/common/Field";
import { Button } from "@/components/common/Button";
import { api, ApiHttpError } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Пароль должен быть не короче 8 символов");
      return;
    }
    if (password !== confirm) {
      setError("Пароли не совпадают");
      return;
    }

    setLoading(true);
    try {
      await api.auth.register(email, password);
      router.push(`/auth/verify?email=${encodeURIComponent(email)}`);
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setError(err.detail);
      } else {
        setError("Неизвестная ошибка");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      tabs="register"
      step="шаг 1 из 3"
      logLines={[
        { color: "var(--dim)", text: "# регистрация" },
        { color: "var(--muted)", text: "[runtime] требуется email + пароль" },
        { text: "" },
        { color: "var(--green)", text: "$ ./khasa register" },
        { color: "var(--muted)", text: "> следующий шаг: " + " код подтверждения" },
        { color: "var(--muted)", text: "> после кода: ожидание аппрува" },
      ]}
      note={
        <Note>
          После регистрации мы пришлём 6-значный код. Далее заявку должен
          одобрить администратор — обычно в течение рабочего дня.
        </Note>
      }
      title={<>Создайте аккаунт.</>}
      subtitle="Email + пароль. Дальше — код подтверждения и аппрув администратора."
    >
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 480 }}>
        <Field
          label="email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          disabled={loading}
        />
        <Field
          label="password"
          name="password"
          autoComplete="new-password"
          placeholder="минимум 8 символов"
          togglePassword
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          disabled={loading}
        />
        <Field
          label="repeat password"
          name="confirm"
          autoComplete="new-password"
          placeholder="ещё раз"
          togglePassword
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          disabled={loading}
        />

        {error && (
          <div
            style={{
              padding: "10px 12px",
              border: "1px solid var(--rule)",
              borderLeft: "3px solid var(--red)",
              background: "var(--surf)",
              fontFamily: "var(--mono)",
              fontSize: 12,
              color: "var(--text)",
            }}
          >
            <span style={{ color: "var(--red)", fontWeight: 700, marginRight: 8 }}>
              [err]
            </span>
            {error}
          </div>
        )}

        <Button type="submit" loading={loading} iconRight="↵">
          создать аккаунт
        </Button>

        <p
          style={{
            fontFamily: "var(--sans)",
            fontSize: 12,
            color: "var(--muted)",
            marginTop: 4,
            lineHeight: 1.55,
          }}
        >
          Создавая аккаунт, вы соглашаетесь с условиями использования
          и политикой обработки данных.
        </p>
      </form>
    </AuthShell>
  );
}
