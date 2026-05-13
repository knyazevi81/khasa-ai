import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Middleware-страж: на сервере у нас нет доступа к localStorage, поэтому
 * мы дублируем факт авторизации в обычный cookie `khasa.auth=1`
 * (см. src/lib/token-storage.ts). Само значение токена в куке не лежит —
 * это просто маркер «авторизован». Полная проверка токена — на бэке.
 */
const PROTECTED = [/^\/chat(\/|$)/, /^\/admin(\/|$)/, /^\/settings(\/|$)/];
const AUTH_PAGES = [/^\/auth(\/|$)/];

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const isAuthed = req.cookies.get("khasa.auth")?.value === "1";

  if (PROTECTED.some((r) => r.test(pathname)) && !isAuthed) {
    const url = req.nextUrl.clone();
    url.pathname = "/auth/login";
    return NextResponse.redirect(url);
  }

  if (AUTH_PAGES.some((r) => r.test(pathname)) && isAuthed && pathname === "/auth/login") {
    // Залогиненного с /auth/login отправим в чат, но verify/pending
    // оставляем доступными (они могут пригодиться для смены email и т.д.)
    const url = req.nextUrl.clone();
    url.pathname = "/chat";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
