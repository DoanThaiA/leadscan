import { redirect } from "next/navigation";

// "Chân dung cơ hội" đã gộp vào mục "Cơ hội phù hợp"
export default function ProfileRedirect() {
  redirect("/thanh-vien/phu-hop");
}
