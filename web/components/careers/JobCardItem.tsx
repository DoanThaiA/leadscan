import { daysLeft, fmtDay, JOB_TYPES, type JobCard } from "@/lib/careers";

/** Nhãn hạn nộp: "Còn 3 ngày" khi sắp hết hạn, ngược lại "Hạn 31/12/2026" */
export function DeadlineTag({ deadline }: { deadline: string | null }) {
  const left = daysLeft(deadline);
  if (left === null) return null;
  const soon = left <= 7;
  return (
    <span className={soon ? "cr-due soon" : "cr-due"}>
      {left <= 0 ? "Hạn cuối hôm nay" : soon ? `Còn ${left} ngày` : `Hạn ${fmtDay(deadline)}`}
    </span>
  );
}

export function JobCardItem({ job }: { job: JobCard }) {
  return (
    <a className={job.cover_image ? "cr-job has-cover" : "cr-job"} href={`/tuyen-dung/${job.slug}`}>
      {job.cover_image ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="cr-job-cover" src={job.cover_image} alt="" loading="lazy" />
      ) : null}
      <div className="cr-job-top">
        {job.department ? <span className="pill-tag">{job.department}</span> : <span />}
        <DeadlineTag deadline={job.deadline} />
      </div>
      <h3>{job.title}</h3>
      {job.summary ? <p>{job.summary}</p> : null}
      <ul className="cr-meta">
        {job.salary ? <li><svg className="icon"><use href="#i-wallet" /></svg>{job.salary}</li> : null}
        {job.location ? <li><svg className="icon"><use href="#i-map" /></svg>{job.location}</li> : null}
        <li><svg className="icon"><use href="#i-brief" /></svg>{JOB_TYPES[job.employment_type] ?? job.employment_type}</li>
        {job.quantity ? <li><svg className="icon"><use href="#i-users" /></svg>Số lượng: {job.quantity}</li> : null}
      </ul>
      <span className="link-arrow">Xem chi tiết <svg className="icon" style={{ width: 16, height: 16 }}><use href="#i-arrow" /></svg></span>
    </a>
  );
}
