import type { MetadataRoute } from "next";

import { fetchJobs } from "@/lib/careers-server";
import { AREA_PAGES, articleAreasFor } from "@/lib/areas";
import { DEFAULT_SECTION, fetchArticles, fetchSections, sectionHref } from "@/lib/blog";
import { INDUSTRY_PAGES } from "@/lib/industries";
import { fetchPublicOpps } from "@/lib/public-opps";
import { SITE_URL } from "@/lib/seo";

// Sitemap gồm trang tĩnh + từng cơ hội đang mở bán + từng vị trí tuyển dụng (lấy từ API mỗi lần Google đọc).
// API lỗi → vẫn trả các trang tĩnh, không làm hỏng sitemap.
export const dynamic = "force-dynamic";

const MAX_OPP_PAGES = 20; // 60 cơ hội/trang → tối đa 1.200 cơ hội

async function oppUrls(): Promise<MetadataRoute.Sitemap> {
  const out: MetadataRoute.Sitemap = [];
  for (let page = 1; page <= MAX_OPP_PAGES; page++) {
    const r = await fetchPublicOpps({ page: String(page), page_size: "60" });
    if (!r) break;
    for (const o of r.items) {
      out.push({ url: `${SITE_URL}/co-hoi/${encodeURIComponent(o.code)}`, lastModified: o.published_at ? new Date(o.published_at) : undefined, changeFrequency: "weekly", priority: 0.6 });
    }
    if (page * r.page_size >= r.total || !r.items.length) break;
  }
  return out;
}

/** Trang ngành / khu vực: chỉ đưa trang đang có cơ hội (trang trống để noindex, không đưa vào sitemap). */
async function topicUrls(): Promise<MetadataRoute.Sitemap> {
  const topics = [
    ...INDUSTRY_PAGES.map((x) => ({ path: `/co-hoi/nganh/${x.slug}`, q: { industry: x.name } })),
    ...AREA_PAGES.map((x) => ({ path: `/co-hoi/khu-vuc/${x.slug}`, q: { places: x.terms.join("|") } })),
  ];
  const rows = await Promise.all(topics.map(async (x) => ({ x, r: await fetchPublicOpps({ ...x.q, page_size: "1" }) })));
  return rows
    .filter(({ r }) => r && r.total > 0)
    .map(({ x, r }) => ({
      url: `${SITE_URL}${x.path}`,
      lastModified: r!.items[0]?.published_at ? new Date(r!.items[0].published_at) : undefined,
      changeFrequency: "daily" as const,
      priority: 0.8,
    }));
}

async function articleUrls(): Promise<(MetadataRoute.Sitemap[number] & { section: string })[]> {
  const out: (MetadataRoute.Sitemap[number] & { section: string })[] = [];
  for (let page = 1; page <= 20; page++) {
    const r = await fetchArticles({ page: String(page), page_size: "60" });
    if (!r) break;
    for (const a of r.items) {
      out.push({ section: a.section, url: `${SITE_URL}${sectionHref(a.section)}/${encodeURIComponent(a.slug)}`, lastModified: new Date(a.updated_at || a.published_at || Date.now()), changeFrequency: "monthly", priority: 0.7 });
    }
    if (page * r.page_size >= r.total || !r.items.length) break;
  }
  return out;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const fixed: MetadataRoute.Sitemap = [
    { url: `${SITE_URL}/`, lastModified: now, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/co-hoi`, lastModified: now, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE_URL}/doi-tac`, lastModified: now, changeFrequency: "monthly", priority: 0.8 },
    { url: `${SITE_URL}/gioi-thieu`, lastModified: now, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/tuyen-dung`, lastModified: now, changeFrequency: "weekly", priority: 0.5 },
  ];
  const [inds, opps, allPosts, jobs, sections] = await Promise.all([
    topicUrls().catch(() => []), oppUrls().catch(() => []), articleUrls().catch(() => []), fetchJobs(), fetchSections(),
  ]);
  const posts = allPosts.filter((p) => p.section === DEFAULT_SECTION);
  const strip = ({ section: _, ...rest }: (typeof allPosts)[number]) => rest;
  const jobUrls: MetadataRoute.Sitemap = (jobs ?? []).map((j) => ({ url: `${SITE_URL}/tuyen-dung/${encodeURIComponent(j.slug)}`, changeFrequency: "weekly", priority: 0.4 }));
  const counts = (await fetchArticles({ section: DEFAULT_SECTION, page_size: "1" }).catch(() => null))?.area_counts ?? {};
  const guideHubs: MetadataRoute.Sitemap = AREA_PAGES.filter((x) => articleAreasFor(x.slug).some((s) => (counts[s] ?? 0) > 0))
    .map((x) => ({ url: `${SITE_URL}/cam-nang/khu-vuc/${x.slug}`, lastModified: posts[0]?.lastModified, changeFrequency: "weekly" as const, priority: 0.6 }));
  const blog: MetadataRoute.Sitemap = posts.length ? [{ url: `${SITE_URL}/cam-nang`, lastModified: posts[0].lastModified, changeFrequency: "weekly", priority: 0.8 }, ...posts.map(strip), ...guideHubs] : [];
  // Danh mục bài viết khác (Tuyển dụng, Tin tức…): trang danh mục + từng bài, chỉ khi đã có bài đang hiện
  const others = allPosts.filter((p) => p.section !== DEFAULT_SECTION);
  const sectionHubs: MetadataRoute.Sitemap = (sections ?? []).filter((x) => x.slug !== DEFAULT_SECTION && x.count > 0)
    .map((x) => ({ url: `${SITE_URL}${sectionHref(x.slug)}`, lastModified: others.find((p) => p.section === x.slug)?.lastModified, changeFrequency: "weekly" as const, priority: 0.6 }));
  return [...fixed, ...blog, ...sectionHubs, ...others.map(strip), ...inds, ...opps, ...jobUrls];
}
