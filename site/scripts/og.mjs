// Open Graph image (1200 x 630) -> public/og.png. Numbers come from public/data/portfolio.json (export);
// the photo is a crop of Commons #3 (an adaptation under CC BY-SA 4.0, credited in the image).
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const P = JSON.parse(readFileSync(`${root}public/data/portfolio.json`, "utf8"));
const photos = JSON.parse(readFileSync(`${root}public/img/photos.json`, "utf8"));
const hero = photos.wm3_victoria_harbour_sunrise;
const f = P.scenarios.ssp245_2050;
const bg = `data:image/webp;base64,${readFileSync(`${root}public/${hero.src.replace(".jpg", "-1600.webp")}`).toString("base64")}`;
const html = `<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Inter:wght@500;600&display=block" rel="stylesheet">
<style>
  html,body{margin:0;width:1200px;height:630px;overflow:hidden;background:#0B1F33}
  .bg{position:absolute;inset:0;background:url('${bg}') center 35%/cover}
  .shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(11,31,51,.97) 0%,rgba(11,31,51,.88) 48%,rgba(11,31,51,.25) 100%)}
  .t{position:absolute;left:72px;top:96px;width:720px;color:#FAFAF7;font-family:Inter,sans-serif}
  .k{color:#7FD1C7;font-weight:600;letter-spacing:.08em;text-transform:uppercase;font-size:20px;margin:0 0 22px}
  h1{font-family:Fraunces,Georgia,serif;font-weight:600;font-size:84px;line-height:1.02;margin:0 0 26px;letter-spacing:-.01em}
  p{font-size:28px;line-height:1.35;margin:0;color:#E6F4F1}
  .brand{position:absolute;left:72px;bottom:46px;font-family:Fraunces,serif;font-size:30px;color:#FAFAF7;display:flex;gap:12px;align-items:center}
  .cr{position:absolute;right:20px;bottom:14px;font:500 13px Inter,sans-serif;color:#A8BCCB}
</style></head><body><div class="bg"></div><div class="shade"></div>
<div class="t"><p class="k">Link REIT · Hong Kong · independent study</p><h1>Small, concentrated, rising.</h1>
<p>${f.n_assets_with_coastal_loss} of ${P.n_assets} properties carry all of the coastal flood risk, and it more than triples by 2050.</p></div>
<div class="brand"><svg width="34" height="22" viewBox="0 0 22 14"><path d="M1 9c3-4 6-4 9 0s6 4 9 0" fill="none" stroke="#FAFAF7" stroke-width="2.2" stroke-linecap="round"/><path d="M1 4c3-3 6-3 9 0s6 3 9 0" fill="none" stroke="#7FD1C7" stroke-width="2.2" stroke-linecap="round"/></svg>Rising Tide</div>
<div class="cr">Photo: ${hero.author}, cropped (adaptation; CC BY-SA 4.0), via Wikimedia Commons</div></body></html>`;
const b = await chromium.launch({ channel: "chrome" });
const p = await b.newPage({ viewport: { width: 1200, height: 630 } });
await p.setContent(html, { waitUntil: "networkidle" });
await p.evaluate(() => document.fonts.ready);
await p.screenshot({ path: `${root}public/og.png` });
await b.close();
console.log("wrote public/og.png");
