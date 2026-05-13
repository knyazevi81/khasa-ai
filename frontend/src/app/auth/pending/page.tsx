"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { AuthShell, Note } from "@/components/auth/AuthShell";
import { Button } from "@/components/common/Button";

export default function PendingPage() {
  const params = useSearchParams();
  const email = params.get("email") ?? "";

  return (
    <AuthShell
      step="шаг 3 из 3"
      logLines={[
        { color: "var(--dim)", text: "# регистрация" },
        { color: "var(--green)", text: "[✓] аккаунт создан" },
        { color: "var(--green)", text: "[✓] email подтверждён" },
        { color: "var(--yellow)", text: "[…] ожидаем аппрува администратора" },
        { text: "" },
        { color: "var(--muted)", text: `> адрес: ${email || "—"}` },
      ]}
      note={
        <Note label="// уведомление">
          Письмо со ссылкой на вход придёт автоматически — как только админ
          подтвердит заявку. Эту страницу можно закрыть.
        </Note>
      }
      title={
        <>
          Заявка <span className="yellow">отправлена</span>.
        </>
      }
      subtitle="Email подтверждён. Теперь администратор должен одобрить вход. В среднем — в течение рабочего дня."
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 18, maxWidth: 480 }}>
        <div
          style={{
            padding: "16px 18px",
            border: "1px solid var(--rule)",
            background: "var(--surf)",
            fontFamily: "var(--mono)",
            fontSize: 12,
            color: "var(--muted)",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <div>
            <span style={{ color: "var(--green)" }}>$</span>{" "}
            <span style={{ color: "var(--text)" }}>khasa --status</span>
          </div>
          <div>
            <span style={{ color: "var(--dim)" }}>{">"}</span> email:{" "}
            <span style={{ color: "var(--text)" }}>{email || "—"}</span>
          </div>
          <div>
            <span style={{ color: "var(--dim)" }}>{">"}</span> верификация:{" "}
            <span style={{ color: "var(--green)" }}>пройдена</span>
          </div>
          <div>
            <span style={{ color: "var(--dim)" }}>{">"}</span> доступ:{" "}
            <span style={{ color: "var(--yellow)" }}>ожидание</span>
          </div>
        </div>

        <div style={{ display: "flex", gap: 10 }}>
          <Link href="/auth/login">
            <Button variant="ghost">на экран входа</Button>
          </Link>
        </div>
      </div>
    </AuthShell>
  );
}
