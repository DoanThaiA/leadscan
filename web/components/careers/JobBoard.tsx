"use client";

import { useMemo, useState } from "react";

import type { JobCard } from "@/lib/careers";

import { JobCardItem } from "./JobCardItem";

/** Lưới vị trí đang tuyển + lọc theo phòng ban (chỉ hiện bộ lọc khi có từ 2 phòng ban). */
export default function JobBoard({ jobs }: { jobs: JobCard[] }) {
  const [dept, setDept] = useState("");
  const depts = useMemo(() => {
    const m = new Map<string, number>();
    for (const j of jobs) if (j.department) m.set(j.department, (m.get(j.department) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [jobs]);
  const shown = dept ? jobs.filter((j) => j.department === dept) : jobs;

  return (
    <>
      {depts.length > 1 ? (
        <div className="cr-filter" role="group" aria-label="Lọc theo phòng ban">
          <button type="button" className={!dept ? "on" : undefined} aria-pressed={!dept} onClick={() => setDept("")}>
            Tất cả <span>{jobs.length}</span>
          </button>
          {depts.map(([d, n]) => (
            <button key={d} type="button" className={dept === d ? "on" : undefined} aria-pressed={dept === d} onClick={() => setDept(d)}>
              {d} <span>{n}</span>
            </button>
          ))}
        </div>
      ) : null}
      <div className="cr-grid">
        {shown.map((j) => (
          <JobCardItem key={j.slug} job={j} />
        ))}
      </div>
    </>
  );
}
