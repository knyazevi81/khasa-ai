/**
 * Дизайн-токены khasa.
 * Синхронизированы с палитрой бэкенда (app/infrastructure/email/service.py)
 * и с макетами фронта (khasa-dark.jsx).
 */

export const KHASA = {
  red: "#C8202B",
  yellow: "#E8B71A",
  green: "#1E7A3C",
} as const;

export const dark = {
  bg: "#0E0D0B",
  surf: "#16140F",
  raised: "#1D1A14",
  text: "#EAE3D2",
  muted: "#8A8170",
  dim: "#5A5346",
  rule: "#2A2620",
} as const;

export type DarkToken = keyof typeof dark;
export type BrandToken = keyof typeof KHASA;
