"use client";

import { useEffect, useState } from "react";

/** Thanh "Ứng tuyển ngay" cố định đáy màn hình điện thoại; ẩn ở đầu trang và khi đang ở form ứng tuyển. */
export default function ApplyBar({ salary }: { salary: string }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const form = document.getElementById("ung-tuyen");
    const onScroll = () => {
      const r = form?.getBoundingClientRect();
      const inForm = r ? r.top < innerHeight * 0.85 : false;
      setShow(scrollY > 420 && !inForm);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className={show ? "m-cta show" : "m-cta"} aria-hidden={!show}>
      <div>
        <small>Thu nhập</small>
        <b>{salary || "Thoả thuận"}</b>
      </div>
      <a href="#ung-tuyen" className="btn btn-primary" tabIndex={show ? 0 : -1}>Ứng tuyển ngay</a>
    </div>
  );
}
