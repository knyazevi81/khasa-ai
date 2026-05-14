/**
 * Дизайн-токены khasa.
 * Палитра подсветлена (пользовательский фидбек), брендовые красный/жёлтый/
 * зелёный оставлены прежними, как в макетах.
 */

export const KHASA = {
  red: "#C8202B",
  yellow: "#E8B71A",
  green: "#1E7A3C",
} as const;

export const dark = {
  bg: "#14120F",
  surf: "#1B1814",
  raised: "#25211A",
  text: "#EFE9D8",
  muted: "#9E957F",
  dim: "#6D6555",
  rule: "#3A332A",
} as const;

export type DarkToken = keyof typeof dark;
export type BrandToken = keyof typeof KHASA;
