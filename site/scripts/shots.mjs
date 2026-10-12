// Screenshots -> docs/internal/screenshots/v2.2/. Needs a static server (`node scripts/serve.mjs build 4180`).
// Each shot lists its viewport widths (v2.2 set: hero 1920 / 1440 / 390 / 360, Story steps 2 and 4 and Explore with a
// property selected at 1440 / 390). usage: node scripts/shots.mjs [baseUrl] [outDir] [only]
import { chromium } from "@playwright/test";
const [,, url = "http://localhost:4180", out = "../docs/internal/screenshots/v2.2", only = ""] = process.argv;
const ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"];
const VP = { 1920: [1920, 1080, "desktop"], 1440: [1440, 900, "desktop"], 390: [390, 844, "mobile"], 360: [360, 780, "mobile"] };
const shots = [
  ["story_hero", "/", null, [1920, 1440, 390, 360]],
  ["story_step2", "/", '.step:has(#s2) .step-card', [1440, 390]],
  ["story_step2_crosssection", "/", '.step[aria-label^="Typhoon"] .step-card', [1440, 390]],
  ["story_step4", "/", '.step:has(#s4) .step-card', [1440, 390]],
  ["story_step4_key_open", "/", '.step:has(#s4) .step-card', [390], true],
  ["explore_asset", "/explore/?asset=129", null, [1440, 390]],
];
const b = await chromium.launch({ channel: "chrome", args: ARGS });
for (const [name, path, sel, widths, openKey] of shots) {
  if (only && !name.includes(only)) continue;
  for (const vw of widths) {
    const [w, h, tag] = VP[vw];
    const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1, isMobile: w < 500, hasTouch: w < 500 });
    p.on("console", (m) => m.type() === "error" && console.log(`  [${tag}/${name}] console error:`, m.text().slice(0, 200)));
    p.on("pageerror", (e) => console.log(`  [${tag}/${name}] pageerror:`, String(e).slice(0, 200)));
    await p.goto(url + path, { waitUntil: "networkidle" });
    // story cards: desktop centred; mobile just below the sticky map + key (where a reader sees them)
    if (sel) { await p.locator(sel).scrollIntoViewIfNeeded(); await p.evaluate((s) => {
      const el = document.querySelector(s);
      if (innerWidth >= 900) return el.scrollIntoView({ block: "center" });
      el.scrollIntoView({ block: "start" });
      const wrap = document.querySelector(".story-map-wrap").getBoundingClientRect();
      scrollBy(0, el.getBoundingClientRect().top - wrap.bottom - 12);
    }, sel); await p.waitForTimeout(300); await p.evaluate(() => scrollBy(0, 1)); }
    await p.waitForTimeout(sel || path.includes("explore") ? 7000 : 2500);
    if (openKey) { await p.getByRole("button", { name: "Key" }).click(); await p.waitForTimeout(300); }
    await p.screenshot({ path: `${out}/${name}_${tag}_${w}.png` });
    await p.close();
  }
}
await b.close();
console.log("done");
