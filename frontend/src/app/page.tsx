import { redirect } from "next/navigation";

export default function HomePage() {
  // На главной просто решаем, куда идти — middleware дополнительно
  // отфильтрует анонимов.
  redirect("/chat");
}
