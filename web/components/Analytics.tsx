"use client";

import { usePathname } from "next/navigation";
import Script from "next/script";
import { useEffect } from "react";

/**
 * Google Analytics 4. Chỉ chạy khi đặt NEXT_PUBLIC_GA_ID (dạng G-XXXXXXXXXX, nhúng lúc build) — để trống thì không tải gì.
 *
 * Không đo các trang riêng tư (admin, cổng thành viên, cổng đối tác): trang chứa thông tin cá nhân / tài chính, đã noindex,
 * và không nên gửi sang bên thứ ba. Vào trang riêng tư từ trang công khai bằng chuyển trang trong ứng dụng thì script đã
 * tải sẵn → bật cờ `ga-disable-<ID>` để GA ngừng gửi (cách Google khuyến nghị), ra lại trang công khai thì tắt cờ.
 * Script tải sau khi trang đã tương tác được (afterInteractive) nên không chặn hiển thị.
 */
const RAW = process.env.NEXT_PUBLIC_GA_ID ?? "";
const GA_ID = /^G-[A-Z0-9]{4,20}$/.test(RAW) ? RAW : "";

const PRIVATE_PREFIXES = ["/admin", "/thanh-vien"];
/** /doi-tac (trang giới thiệu chương trình) công khai; mọi trang con /doi-tac/… là cổng đối tác hoặc điều khoản → không đo */
const isPrivate = (p: string) => PRIVATE_PREFIXES.some((x) => p === x || p.startsWith(`${x}/`)) || p.startsWith("/doi-tac/");

export default function Analytics() {
  const path = usePathname();
  const off = isPrivate(path);

  useEffect(() => {
    if (GA_ID) (window as unknown as Record<string, unknown>)[`ga-disable-${GA_ID}`] = off;
  }, [off]);

  if (!GA_ID || off) return null;
  return (
    <>
      <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
      <Script id="ga-init" strategy="afterInteractive">
        {`window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${GA_ID}');`}
      </Script>
    </>
  );
}
