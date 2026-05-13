"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState, useCallback } from "react";
import { AuthShell, Note } from "@/components/auth/AuthShell";
import { CodeField } from "@/components/common/CodeField";
import { Button } from "@/components/common/Button";
import { api, ApiHttpError } from "@/lib/api";

export default function VerifyPage() {
  const router = useRouter();
  const params = useSearchParams();
  const email = params.get("email") ?? "";

  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(60);

  const verify = useCallback(
    async (value: string) => {
      if (!email) return;
      setLoading(true);
      setError(null);
      try {
        await api.auth.verifyEmail(email, value);
        router.push(`/auth/pending?email=${encodeURIComponent(email)}`);
      } catch (err) {
        if (err instanceof ApiHttpError) {
          setError(err.detail);
        } else {
          setError("Неизвестная ошибка");
        }
      } finally {
        setLoading(false);
      }
    },
    [email, router],
  );

  const resend = async () => {
    try {
      await api.auth.resendCode(email);
      setResendCooldown(60);
      setError(null);
    } catch (err) {
      if (err instanceof ApiHttpError) {
        setError(err.detail);
      }
    }
  };

  return (
    <AuthShell
      step="шаг 2 из 3"
      logLines={[
        { color: "var(--dim)", text: "# регистрация" },
        { color: "var(--green)", text: "[✓] аккаунт создан" },
        { color: "var(--yellow)", text: "[…] ожидание кода" },
        { text: "" },
        { color: "var(--muted)", text: `> адрес: ${email || "—"}` },
        { color: "var(--muted)", text: "> срок действия: 15 минут" },
      ]}
      note={
        <Note label="// что дальше">
          После ввода кода администратор увидит вашу заявку. Как только её
          одобрят — вы получите письмо со ссылкой на вход.
        </Note>
      }
      title={
        <>
          Подтвердите <span className="yellow">email</span>.
        </>
      }
      subtitle="Мы отправили 6-значный код. Введите его ниже — поле само перейдёт дальше."
    >
      <div style={{ maxWidth: 480, display: "flex", flexDirection: "column", gap: 18 }}>
        <CodeField
          value={code}
          onChange={(v) => {
            setCode(v);
            setError(null);
          }}
          onComplete={verify}
          email={email}
          error={!!error}
          resendInSeconds={resendCooldown}
          onResend={resend}
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

        <div style={{ display: "flex", gap: 10 }}>
          <Button
            onClick={() => verify(code)}
            disabled={code.length !== 6 || loading}
            loading={loading}
            iconRight="↵"
          >
            подтвердить
          </Button>
          <Button variant="ghost" onClick={() => router.push("/auth/register")}>
            назад
          </Button>
        </div>
      </div>
    </AuthShell>
  );
}
