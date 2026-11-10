"use client";

import { useEffect } from "react";

/** Hiệu ứng trang trí: tia sáng hero, đường nối hub nguồn dữ liệu, hiện dần khi cuộn, bộ đếm số, đánh dấu tab quy trình. */
export default function LandingEffects() {
  useEffect(() => {
    function drawRays() {
      const svg = document.getElementById("rays") as SVGSVGElement | null;
      if (!svg) return;
      const w = svg.clientWidth, h = svg.clientHeight;
      svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
      const cx = w / 2, cy = h * 0.32;
      let s = '<defs><radialGradient id="rg" cx="50%" cy="32%" r="60%"><stop offset="35%" stop-color="#004B87" stop-opacity="0"/><stop offset="100%" stop-color="#004B87" stop-opacity=".35"/></radialGradient></defs>';
      const n = 30;
      for (let i = 0; i < n; i++) {
        const a = (i / n) * Math.PI * 2 + 0.08;
        if (Math.abs(Math.sin(a)) > 0.82) continue;
        const r1 = Math.min(w, 1200) * 0.42, r2 = Math.max(w, h) * 1.1;
        s += `<line x1="${cx + Math.cos(a) * r1}" y1="${cy + Math.sin(a) * r1 * 0.62}" x2="${cx + Math.cos(a) * r2}" y2="${cy + Math.sin(a) * r2 * 0.62}" stroke="url(#rg)" stroke-width="1"/>`;
      }
      svg.innerHTML = s;
    }

    function drawHub() {
      const hub = document.getElementById("hub"), svg = document.getElementById("hubLines");
      if (!hub || !svg) return;
      const b = hub.getBoundingClientRect(), cx = b.width / 2, cy = b.height / 2;
      svg.setAttribute("viewBox", `0 0 ${b.width} ${b.height}`);
      let s = "";
      hub.querySelectorAll(".node").forEach((node) => {
        const r = node.getBoundingClientRect();
        s += `<line x1="${cx}" y1="${cy}" x2="${r.left - b.left + r.width / 2}" y2="${r.top - b.top + r.height / 2}" stroke="#fff" stroke-width="1.5" stroke-dasharray="4 4" opacity=".9"/>`;
      });
      svg.innerHTML = s;
    }

    let raf = 0;
    const redraw = () => {
      drawRays();
      drawHub();
    };
    const onResize = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(redraw);
    };
    redraw();
    document.fonts?.ready.then(redraw);
    window.addEventListener("load", redraw);
    window.addEventListener("resize", onResize);

    // Hiện dần khi cuộn + bộ đếm
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          e.target.classList.add("in");
          e.target.querySelectorAll<HTMLElement>("[data-count]").forEach((el) => {
            const end = Number(el.dataset.count), suf = el.dataset.suffix || "";
            let t0: number | null = null;
            const step = (t: number) => {
              t0 ??= t;
              const p = Math.min((t - t0) / 1200, 1);
              el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3))) + suf;
              if (p < 1) requestAnimationFrame(step);
            };
            requestAnimationFrame(step);
          });
          io.unobserve(e.target);
        }),
      { threshold: 0.12 },
    );
    document.querySelectorAll(".reveal").forEach((el) => io.observe(el));

    // Đánh dấu tab của bước quy trình đang xem
    const tabs = Array.from(document.querySelectorAll(".wf-tab"));
    const spy = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => {
          if (e.isIntersecting) tabs.forEach((t) => t.classList.toggle("active", t.getAttribute("href") === "#" + e.target.id));
        }),
      { rootMargin: "-45% 0px -50% 0px" },
    );
    ["b1", "b2", "b3", "b4"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) spy.observe(el);
    });

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("load", redraw);
      window.removeEventListener("resize", onResize);
      io.disconnect();
      spy.disconnect();
    };
  }, []);

  return null;
}
