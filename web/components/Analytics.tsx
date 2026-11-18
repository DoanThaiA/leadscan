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

const GTM_ID = "GTM-WCPQ9TCT";

const PRIVATE_PREFIXES = ["/admin", "/thanh-vien"];
/** /doi-tac (trang giới thiệu chương trình) công khai; mọi trang con /doi-tac/… là cổng đối tác hoặc điều khoản → không đo */
const isPrivate = (p: string) => PRIVATE_PREFIXES.some((x) => p === x || p.startsWith(`${x}/`)) || p.startsWith("/doi-tac/");

export default function Analytics() {
  const path = usePathname();
  const off = isPrivate(path);

  useEffect(() => {
    if (GA_ID) (window as unknown as Record<string, unknown>)[`ga-disable-${GA_ID}`] = off;
  }, [off]);

  if (off) return null;
  return (
    <>
      {/* Google Tag Manager — khởi tạo chuẩn (gtm.start) rồi tải container; GA4 cấu hình trong GTM */}
      <Script id="gtm-init" strategy="afterInteractive">
        {`window.dataLayer=window.dataLayer||[];window.dataLayer.push({'gtm.start':new Date().getTime(),event:'gtm.js'});var s=document.createElement('script');s.async=true;s.src='https://www.googletagmanager.com/gtm.js?id=${GTM_ID}';document.head.appendChild(s);`}
      </Script>
      {GA_ID && (
        <>
      <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_ID}`} strategy="afterInteractive" />
      <Script id="ga-init" strategy="afterInteractive">
        {`window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','${GA_ID}');`}
      </Script>
        </>
      )}
    </>
  );
}
