import { readFile } from "node:fs/promises";
import path from "node:path";

import sharp from "sharp";

import { fetchJob } from "@/lib/careers-server";

/** Ảnh xem trước khi chia sẻ link (Zalo, Facebook, Messenger…): JPG 1200×630.
 *  Ảnh bìa thường là WebP — nhiều app chat không hiển thị WebP trong khung preview → chuyển sang JPG tại đây. */

const PUBLIC_DIR = path.join(process.cwd(), "public");
const FALLBACK = "/brand/leadscan-og.jpg";

async function loadSource(src: string): Promise<Buffer> {
  if (/^https?:\/\//i.test(src)) {
    const r = await fetch(src, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return Buffer.from(await r.arrayBuffer());
  }
  const file = path.join(PUBLIC_DIR, decodeURIComponent(src.split(/[?#]/)[0]));
  if (!file.startsWith(PUBLIC_DIR + path.sep)) throw new Error("Đường dẫn ảnh không hợp lệ");
  return readFile(file);
}

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const job = await fetchJob((await params).slug).catch(() => null);
  if (!job) return new Response("Not found", { status: 404 });

  let jpg: Buffer;
  try {
    jpg = await sharp(await loadSource(job.cover_image || FALLBACK))
      .rotate()
      .resize(1200, 630, { fit: "cover", position: "centre" })
      .flatten({ background: "#ffffff" })
      .jpeg({ quality: 82, mozjpeg: true })
      .toBuffer();
  } catch (e) {
    console.error(`Không tạo được ảnh chia sẻ cho ${job.slug}:`, e);
    jpg = await readFile(path.join(PUBLIC_DIR, FALLBACK));
  }

  return new Response(new Uint8Array(jpg), {
    headers: {
      "Content-Type": "image/jpeg",
      "Content-Length": String(jpg.length),
      "Cache-Control": "public, max-age=3600, s-maxage=86400",
    },
  });
}
