"use client";

import { useEffect, useState } from "react";

/** Thanh "Đăng ký" cố định ở đáy màn hình điện thoại; ẩn khi ở hero, form đăng ký hoặc footer. */
export default function MobileCta() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const hero = document.querySelector<HTMLElement>(".hero");
    const foot = document.querySelector("footer");
    const reg = document.getElementById("dang-ky");
    const onScroll = () => {
      if (!hero || !foot || !reg) return;
      const r = reg.getBoundingClientRect();
      const inForm = r.top < innerHeight * 0.6 && r.bottom > innerHeight * 0.2;
      setShow(scrollY > hero.offsetHeight * 0.6 && foot.getBoundingClientRect().top > innerHeight && !inForm);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className={show ? "m-cta show" : "m-cta"} id="mcta" aria-hidden={!show}>
      <div><small>Phiếu cơ hội chỉ từ</small><b>29.000đ</b></div>
      <a href="#dang-ky" className="btn btn-primary" tabIndex={show ? 0 : -1}>Đăng ký thành viên</a>
    </div>
  );
}
