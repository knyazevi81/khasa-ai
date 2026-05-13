/**
 * Хранение JWT-токенов. localStorage — простой компромисс для MVP:
 *   + переживает обновление страницы,
 *   + Next.js middleware читает их через дублирование в cookie ниже,
 *   - чувствителен к XSS (поэтому строгий CSP в проде — обязателен).
 *
 * Дублируем access-токен в http-only-cookie через /api/proxy/set-cookie
 * (см. src/app/api/proxy/set-cookie/route.ts) — это позволяет middleware
 * Next.js защищать /admin и /chat от анонимных пользователей без обращения
 * к localStorage (он на сервере недоступен).
 */

const ACCESS_KEY = "khasa.access";
const REFRESH_KEY = "khasa.refresh";

export const tokenStorage = {
  get access(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(ACCESS_KEY);
  },
  get refresh(): string | null {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(REFRESH_KEY);
  },
  set(pair: { access_token: string; refresh_token: string }): void {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(ACCESS_KEY, pair.access_token);
    window.localStorage.setItem(REFRESH_KEY, pair.refresh_token);
    // Дубликат в cookie — для middleware
    document.cookie = `khasa.auth=1; path=/; max-age=2592000; SameSite=Lax`;
  },
  clear(): void {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem(ACCESS_KEY);
    window.localStorage.removeItem(REFRESH_KEY);
    document.cookie = "khasa.auth=; path=/; max-age=0; SameSite=Lax";
  },
};
