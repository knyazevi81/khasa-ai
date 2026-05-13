from __future__ import annotations

import logging

import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.domain.interface.email import AbstractEmailService
from app.infrastructure.config.config import Settings

logger = logging.getLogger(__name__)


# ── Палитра (синхронизирована с frontend src/styles/tokens.ts) ────────────────
BRAND = {
    "red":    "#C8202B",
    "yellow": "#E8B71A",
    "green":  "#1E7A3C",
    "bg":     "#0E0D0B",
    "surf":   "#16140F",
    "raised": "#1D1A14",
    "text":   "#EAE3D2",
    "muted":  "#8A8170",
    "dim":    "#5A5346",
    "rule":   "#2A2620",
}


def _wrap(title: str, body_html: str, support_email: str) -> str:
    """
    Общий каркас письма. Email-клиенты — это 1998-й HTML: только таблицы,
    inline-стили, никаких flex/grid. Все цвета захардкожены.
    """
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:{BRAND['bg']};font-family:'SF Mono','Menlo','Consolas','Courier New',monospace;color:{BRAND['text']};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BRAND['bg']};padding:48px 16px;">
  <tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:{BRAND['surf']};border:1px solid {BRAND['rule']};">

      <!-- ── header ── -->
      <tr>
        <td style="padding:22px 28px;border-bottom:1px solid {BRAND['rule']};">
          <table role="presentation" cellpadding="0" cellspacing="0">
            <tr>
              <td style="padding-right:14px;vertical-align:middle;">
                <table role="presentation" cellpadding="0" cellspacing="0">
                  <tr><td style="width:9px;height:9px;background:{BRAND['red']};line-height:9px;font-size:1px;">&nbsp;</td></tr>
                  <tr><td style="height:2px;line-height:2px;font-size:1px;">&nbsp;</td></tr>
                  <tr><td style="width:9px;height:9px;background:{BRAND['yellow']};line-height:9px;font-size:1px;">&nbsp;</td></tr>
                  <tr><td style="height:2px;line-height:2px;font-size:1px;">&nbsp;</td></tr>
                  <tr><td style="width:9px;height:9px;background:{BRAND['green']};line-height:9px;font-size:1px;">&nbsp;</td></tr>
                </table>
              </td>
              <td style="vertical-align:middle;">
                <div style="font-size:22px;font-weight:700;color:{BRAND['text']};letter-spacing:-0.04em;line-height:1;">khasa</div>
                <div style="font-size:10px;color:{BRAND['dim']};letter-spacing:0.18em;text-transform:uppercase;margin-top:4px;">// умный ассистент</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- ── body ── -->
      <tr>
        <td style="padding:32px 28px;color:{BRAND['text']};">
          {body_html}
        </td>
      </tr>

      <!-- ── footer ── -->
      <tr>
        <td style="padding:16px 28px;background:{BRAND['bg']};border-top:1px solid {BRAND['rule']};">
          <div style="font-size:10px;color:{BRAND['dim']};letter-spacing:0.14em;text-transform:uppercase;">
            khasa &middot; <a href="mailto:{support_email}" style="color:{BRAND['muted']};text-decoration:none;">{support_email}</a>
          </div>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


def _h2(text: str) -> str:
    return (
        f"<h2 style=\"margin:0 0 12px;font-size:20px;font-weight:700;color:{BRAND['text']};"
        f"letter-spacing:-0.01em;font-family:'Inter',-apple-system,system-ui,sans-serif;\">{text}</h2>"
    )


def _p(text: str) -> str:
    return (
        f"<p style=\"margin:0 0 16px;font-size:14px;line-height:1.65;color:{BRAND['muted']};"
        f"font-family:'Inter',-apple-system,system-ui,sans-serif;\">{text}</p>"
    )


def _shell_line(prompt_char: str, prompt_color: str, body: str) -> str:
    return (
        f"<div style=\"font-size:12px;color:{BRAND['muted']};line-height:1.7;\">"
        f"<span style=\"color:{prompt_color};font-weight:700;\">{prompt_char}</span> "
        f"<span style=\"color:{BRAND['text']};\">{body}</span>"
        f"</div>"
    )


def _code_block(code: str) -> str:
    """Большие цифры кода в стиле DarkCodeField из макета."""
    digits = "".join(
        f"<td align=\"center\" valign=\"middle\" "
        f"style=\"width:56px;height:64px;border:1.5px solid {BRAND['green']};"
        f"background:{BRAND['bg']};font-size:30px;font-weight:700;color:{BRAND['text']};"
        f"letter-spacing:-0.02em;font-family:'SF Mono','Menlo',monospace;\">{d}</td>"
        f"<td style=\"width:6px;line-height:1px;font-size:1px;\">&nbsp;</td>"
        for d in code
    )
    return (
        f"<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" "
        f"style=\"margin:8px 0 22px;\">"
        f"<tr>{digits}</tr></table>"
    )


def _button(text: str, href: str, color: str = BRAND["green"]) -> str:
    return (
        f"<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" "
        f"style=\"margin:8px 0 4px;\"><tr><td>"
        f"<a href=\"{href}\" style=\"display:inline-block;background:{color};color:#fff;"
        f"text-decoration:none;padding:13px 24px;font-size:12px;font-weight:700;"
        f"letter-spacing:0.1em;text-transform:uppercase;"
        f"font-family:'SF Mono','Menlo',monospace;\">{text} &#8629;</a>"
        f"</td></tr></table>"
    )


def _note(text: str, accent: str = BRAND["yellow"]) -> str:
    return (
        f"<table role=\"presentation\" cellpadding=\"0\" cellspacing=\"0\" "
        f"style=\"margin:16px 0;\"><tr>"
        f"<td style=\"padding:12px 14px;border:1px solid {BRAND['rule']};"
        f"border-left:3px solid {accent};background:{BRAND['raised']};\">"
        f"<div style=\"color:{accent};font-size:10px;font-weight:700;letter-spacing:0.16em;"
        f"text-transform:uppercase;margin-bottom:4px;\">// заметка</div>"
        f"<div style=\"font-size:13px;color:{BRAND['muted']};line-height:1.6;"
        f"font-family:'Inter',-apple-system,sans-serif;\">{text}</div>"
        f"</td></tr></table>"
    )


# ── Service ──────────────────────────────────────────────────────────────────


class EmailService(AbstractEmailService):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def _send(self, to: str | list[str], subject: str, html: str) -> None:
        if not self._settings.EMAIL_ENABLED:
            logger.info("email.disabled to=%s subject=%s", to, subject)
            return

        recipients = [to] if isinstance(to, str) else to
        if not recipients:
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._settings.EMAIL_FROM
        msg["To"] = ", ".join(recipients)
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            await aiosmtplib.send(
                msg,
                hostname=self._settings.SMTP_HOST,
                port=self._settings.SMTP_PORT,
                username=self._settings.SMTP_USER or None,
                password=self._settings.SMTP_PASS.get_secret_value() or None,
                use_tls=self._settings.SMTP_USE_TLS,
                start_tls=False if self._settings.SMTP_USE_TLS else None,
            )
            logger.info("email.sent to=%s subject=%s", recipients, subject)
        except Exception as exc:
            logger.error("email.failed to=%s error=%s", recipients, exc)

    # ── Шаблоны ──────────────────────────────────────────────────────────────

    async def send_verification_code(self, to: str, code: str, ttl_minutes: int) -> None:
        body = (
            _shell_line("$", BRAND["green"], "./khasa verify-email")
            + _shell_line(">", BRAND["muted"], f"адресат: <span style='color:{BRAND['text']}'>{to}</span>")
            + _shell_line(">", BRAND["muted"], "тип: <span style='color:" + BRAND["yellow"] + "'>email-код</span>")
            + "<div style='height:18px;line-height:1px;font-size:1px;'>&nbsp;</div>"
            + _h2("Код для подтверждения")
            + _p(
                f"Ваш одноразовый код. Введите его на экране подтверждения email — "
                f"код действителен <strong style=\"color:{BRAND['text']}\">{ttl_minutes} минут</strong>."
            )
            + _code_block(code)
            + _note(
                "Если вы не регистрировались в khasa — просто игнорируйте это письмо. "
                "Код истечёт, аккаунт не создастся."
            )
        )
        html = _wrap("Код подтверждения — khasa", body, self._settings.SUPPORT_EMAIL)
        await self._send(to, "Код подтверждения — khasa", html)

    async def send_registration_pending_approval(self, to: str) -> None:
        body = (
            _shell_line("✓", BRAND["green"], "email подтверждён")
            + _shell_line(">", BRAND["muted"], "статус: <span style='color:" + BRAND["yellow"] + "'>ожидает одобрения</span>")
            + "<div style='height:18px;line-height:1px;font-size:1px;'>&nbsp;</div>"
            + _h2("Заявка отправлена")
            + _p(
                "Email подтверждён. Теперь администратор должен одобрить ваш аккаунт. "
                "Как только это произойдёт — мы пришлём отдельное письмо со ссылкой на вход."
            )
            + _note(
                "В среднем заявки одобряются в течение рабочего дня. "
                "Если что-то долго — напишите на support."
            )
        )
        html = _wrap("Заявка отправлена — khasa", body, self._settings.SUPPORT_EMAIL)
        await self._send(to, "Заявка отправлена — khasa", html)

    async def send_account_activated(self, to: str) -> None:
        body = (
            _shell_line("✓", BRAND["green"], "аккаунт активирован")
            + _shell_line(">", BRAND["muted"], f"вход: <span style='color:{BRAND['text']}'>{self._settings.FRONTEND_URL}</span>")
            + "<div style='height:18px;line-height:1px;font-size:1px;'>&nbsp;</div>"
            + _h2("Доступ открыт")
            + _p(
                "Ваш аккаунт khasa одобрен администратором. Можно входить — "
                "память, ветки и кастомные промпты ждут."
            )
            + _button("Войти в khasa", f"{self._settings.FRONTEND_URL}/auth/login", BRAND["green"])
        )
        html = _wrap("Аккаунт активирован — khasa", body, self._settings.SUPPORT_EMAIL)
        await self._send(to, "Аккаунт активирован — khasa", html)

    async def send_password_changed(self, to: str) -> None:
        body = (
            _shell_line("!", BRAND["yellow"], "password updated")
            + "<div style='height:18px;line-height:1px;font-size:1px;'>&nbsp;</div>"
            + _h2("Пароль изменён")
            + _p(
                "Пароль от вашего аккаунта khasa был изменён. Если это были не вы — "
                f"немедленно напишите на <a href=\"mailto:{self._settings.SUPPORT_EMAIL}\" "
                f"style=\"color:{BRAND['yellow']}\">{self._settings.SUPPORT_EMAIL}</a>."
            )
            + _note(
                "Прошлая сессия не сбрасывается автоматически — если вы сменили пароль с другого "
                "устройства, выйдите из старых сессий через настройки.",
                accent=BRAND["red"],
            )
        )
        html = _wrap("Пароль изменён — khasa", body, self._settings.SUPPORT_EMAIL)
        await self._send(to, "Пароль изменён — khasa", html)

    async def send_custom(self, to: str | list[str], subject: str, message: str) -> None:
        body = _h2(subject) + _p(message.replace("\n", "<br>"))
        html = _wrap(subject, body, self._settings.SUPPORT_EMAIL)
        await self._send(to, f"{subject} — khasa", html)
