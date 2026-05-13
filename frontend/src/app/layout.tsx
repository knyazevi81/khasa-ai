import type { Metadata } from "next";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "khasa — умный ассистент",
  description: "Один чат с памятью, графом веток и панелью артефактов",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
