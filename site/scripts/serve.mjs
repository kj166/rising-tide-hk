// Minimal static server for a built site directory (tests, Lighthouse). usage: node scripts/serve.mjs <dir> <port> [base]
// With a base (e.g. /rising-tide-hk) the site is served only under that path, like GitHub Pages; anything else is 404.
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { gzipSync } from "node:zlib";
const [,, dir = "build", port = "4180", base = ""] = process.argv;
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".geojson": "application/geo+json", ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".svg": "image/svg+xml", ".txt": "text/plain" };
createServer(async (req, res) => {
  let p = normalize(decodeURIComponent(new URL(req.url, "http://x").pathname)).replace(/^(\.\.[/\\])+/, "");
  if (base) {
    if (p === base) { res.writeHead(301, { Location: `${base}/` }); return res.end(); }
    if (!p.startsWith(`${base}/`)) { res.writeHead(404, { "Content-Type": "text/plain" }); return res.end("not found (outside base path)"); }
    p = p.slice(base.length);
  }
  let f = join(dir, p);
  try {
    if ((await stat(f)).isDirectory()) {
      if (!p.endsWith("/")) { res.writeHead(301, { Location: `${base}${p}/` }); return res.end(); }
      f = join(f, "index.html");
    }
    let body = await readFile(f);
    const type = TYPES[extname(f)] ?? "application/octet-stream";
    const headers = { "Content-Type": type, "Cache-Control": "max-age=3600" };
    // gzip text like GitHub Pages does
    if (/text|json|javascript|svg/.test(type) && /gzip/.test(req.headers["accept-encoding"] ?? "")) { body = gzipSync(body); headers["Content-Encoding"] = "gzip"; }
    res.writeHead(200, headers);
    res.end(body);
  } catch { res.writeHead(404, { "Content-Type": "text/plain" }); res.end("not found"); }
}).listen(+port, () => console.log(`serving ${dir} on http://localhost:${port}`));
