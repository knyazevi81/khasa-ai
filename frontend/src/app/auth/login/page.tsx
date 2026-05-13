"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AuthShell, Note } from "@/components/auth/AuthShell";
import { Field } from "@/components/common/Field";
import { Button } from "@/components/common/Button";
import { useAuthStore } from "@/lib/auth-store";
import { ApiHttpError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      router.push("/chat");
    } catch (err) {
      if (err instanceof ApiHttpError) {
        // Бэк отдаёт три разных смысла; уведём юзера туда, где он сможет
        // что-то сделать.
        if (err.detail.toLowerCase().includes("email") && err.detail.toLowerCase().includes("подтверж")) {
          router.push(`/auth/verify?email=${encodeURIComponent(email)}`);
          return;
        }
        if (err.detail.toLowerCase().includes("ожидает одобрения")) {
          router.push(`/auth/pending?email=${encodeURIComponent(email)}`);
          return;
        }
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
      tabs="login"
      step="режим: вход"
      logLines={[
        { color: "var(--dim)", text: "# session boot" },
        { color: "var(--muted)", text: "[runtime] ядро загружено" },
        { color: "var(--muted)", text: "[runtime] требуется аутентификация" },
        { text: "" },
        { color: "var(--green)", text: "$ ./khasa login" },
        { color: "var(--muted)", text: "> провайдер: email + пароль" },
      ]}
      note={
        <Note>
          После входа все ваши чаты, ветки и кастомные промпты будут восстановлены.
        </Note>
      }
      title={
        <>
          <span className="green">{">"}</span> С возвращением.
        </>
      }
      subtitle="Войдите, чтобы продолжить — все ветки и кастомные промпты на месте."
    >
      <form className="form" onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 480 }}>
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
          autoComplete="current-password"
          placeholder="••••••••"
          togglePassword
          value={password}
          onChange={(e) => setPassword(e.target.value)}
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
          войти в khasa
        </Button>
      </form>
    </AuthShell>
  );
}
