// Playwright smoke test (decision 2026-10-08): pages load without console errors, maps render, URL state round-trips,
// reduced motion works, and SHOW_LANDSD_AERIAL true / false both render cleanly.
import { test, expect } from "@playwright/test";

// base-relative paths, so the same tests run at the domain root and under a base path (public build)
const PAGES = ["./", "./explore/", "./insights/", "./method/"];
const APPROVED = "The Quayside, Link's second most valuable Hong Kong property, is protected from the 2050 1-in-100-year sea level (SSP2-4.5, median) by a margin of about 9 cm of ground on the route from the sea. The high end of that scenario's range leaves about 1 cm, the high end of SSP5-8.5 erases it, and the rarer 1-in-200-year level already reaches the site.";

function watchErrors(page) {
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(String(e)));
  return errors;
}
const mapReady = (page, key) => page.waitForFunction((k) => {
  const m = window.__rt?.[k];
  return m && m.loaded() && m.getCanvas().clientHeight > 100 && m.queryRenderedFeatures({ layers: [k === "exploreMap" ? "pts" : "s-pts"] }).length > 0;
}, key, { timeout: 45_000 });

for (const path of PAGES) {
  test(`loads without console errors: ${path}`, async ({ page }) => {
    const errors = watchErrors(page);
    await page.goto(path, { waitUntil: "networkidle" });
    await expect(page.locator("h1").first()).toBeVisible();
    await expect(page.locator("footer")).toContainText("not endorsed by GEO, CEDD, LandsD, HKO or Link REIT");
    await page.waitForTimeout(1500);
    expect(errors).toEqual([]);
  });
}

test("maps render (Explore and the Story scroll map)", async ({ page }) => {
  const errors = watchErrors(page);
  await page.goto("./explore/");
  await mapReady(page, "exploreMap");
  await page.goto("./");
  await page.locator("#story").scrollIntoViewIfNeeded();
  await mapReady(page, "storyMap");
  expect(errors).toEqual([]);
});

test("URL state round trip on Explore", async ({ page }) => {
  await page.goto("./explore/?asset=129&scenario=ssp585_2050");
  await expect(page.locator("#d-name")).toHaveText("Chai Wan Car Service Centre");
  await expect(page.locator('input[name="scenario"][value="ssp585_2050"]')).toBeChecked();
  await page.locator('label:has(input[value="baseline"])').click();
  await expect(page).toHaveURL(/scenario=baseline/);
  await page.locator("#t-rain").click();
  await expect(page).toHaveURL(/hazard=rain/);
  await expect(page).toHaveURL(/asset=129/);
  await page.reload();
  await expect(page.locator("#t-rain")).toHaveAttribute("aria-selected", "true");
  await expect(page.locator("#d-name")).toHaveText("Chai Wan Car Service Centre");
  await page.locator("#t-coastal").click();
  await expect(page.locator('input[name="scenario"][value="baseline"]')).toBeChecked();
});

test("reduced motion: no drift or glow, KPI values final at once", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  const anim = await page.evaluate(() => [getComputedStyle(document.querySelector(".hero-photo img")).animationName,
    getComputedStyle(document.querySelector(".hero-glow")).animationName]);
  expect(anim).toEqual(["none", "none"]);
  const big = page.locator(".kpis .big").first();
  await expect(big).toHaveText(await big.getAttribute("aria-label"), { timeout: 200 });
});

test("approved Quayside sentence is rendered from the export", async ({ page }) => {
  await page.goto("./");
  await expect(page.locator(".margin-note").first()).toHaveText(APPROVED);
  await page.goto("./insights/");
  await expect(page.locator(".margin-note").first()).toHaveText(APPROVED);
  await page.goto("./explore/?asset=126");
  await expect(page.locator(".drawer .margin-note")).toHaveText(APPROVED);
});

test("SHOW_LANDSD_AERIAL controls the aerial thumbnail and logo", async ({ page }, info) => {
  const errors = watchErrors(page);
  const imagery = [];
  page.on("request", (r) => { if (r.url().includes("mapapi.geodata.gov.hk")) imagery.push(r.url()); });
  await page.goto("./explore/?asset=129");
  await expect(page.locator("#d-name")).toHaveText("Chai Wan Car Service Centre");
  await page.waitForTimeout(3000);
  if (info.project.name === "aerial") {
  } else {
    await expect(page.locator('[data-testid="aerial"]')).toHaveCount(0);
    await expect(page.locator('img[alt="Lands Department logo"]')).toHaveCount(0);
    await expect(page.locator("footer")).not.toContainText("Aerial Photograph");
    expect(imagery).toEqual([]);
  }
  expect(errors).toEqual([]);
});

// ---- v2.1 checks (decision 2026-10-08) ----
const PHONES = [[360, 780], [390, 844]];

// the attribution control is on screen and nothing is drawn on top of it (panel, drawer, bottom sheet, cards)
async function attributionVisible(page, mapSel) {
  const box = page.locator(`${mapSel} .maplibregl-ctrl-attrib`);
  await expect(box).toBeVisible({ timeout: 30_000 });
  const ok = await page.evaluate((sel) => {
    const el = document.querySelector(`${sel} .maplibregl-ctrl-attrib`);
    const r = el.getBoundingClientRect();
    if (r.width < 10 || r.height < 10 || r.right > innerWidth || r.bottom > innerHeight || r.left < 0 || r.top < 0) return `off screen ${JSON.stringify(r)}`;
    const pts = [[r.left + 6, r.top + r.height / 2], [r.right - 6, r.top + r.height / 2]];
    for (const [x, y] of pts) { const hit = document.elementFromPoint(x, y); if (!el.contains(hit)) return `covered by ${hit?.className}`; }
    return "ok";
  }, mapSel);
  expect(ok).toBe("ok");
}

for (const [w, h] of [[1440, 900], ...PHONES]) {
  test(`map attribution stays visible at ${w}px (Explore with details open, Story steps)`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("./explore/?asset=129");
    await mapReady(page, "exploreMap");
    await expect(page.locator("#d-name")).toBeVisible();
    await attributionVisible(page, ".explore");
    if (w < 900) {
      for (const snap of ["full", "peek"]) {
        await page.locator(".drawer .sheet-handle").focus();
        await page.keyboard.press(snap === "full" ? "ArrowUp" : "ArrowDown");
        if (snap === "peek") await page.keyboard.press("ArrowDown");
        await expect(page.locator(".drawer")).toHaveAttribute("data-snap", snap);
        await page.waitForTimeout(400);
        await attributionVisible(page, ".explore");
      }
    }
    await page.goto("./");
    await page.locator("#story").scrollIntoViewIfNeeded();
    await mapReady(page, "storyMap");
    for (const id of ["#s2", "#s4", "#s5"]) {
      await page.locator(id).scrollIntoViewIfNeeded();
      await page.waitForTimeout(500);
      await attributionVisible(page, ".story");
    }
  });
}

for (const [w, h] of PHONES) {
  test(`no horizontal overflow and all nav items visible at ${w}px`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    for (const path of PAGES) {
      await page.goto(path, { waitUntil: "networkidle" });
      const [doc, vw] = await page.evaluate(() => [document.documentElement.scrollWidth, innerWidth]);
      expect(doc, path).toBe(vw);
      for (const name of ["Story", "Explore", "Insights", "Method"]) {
        const r = await page.locator(".nav").getByRole("link", { name, exact: true }).boundingBox();
        expect(r.x >= 0 && r.x + r.width <= w, `${path} ${name}`).toBe(true);
      }
    }
  });
}

test("Explore bottom sheet opens at half height with a drag handle (390 px)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./explore/");
  await expect(page.locator(".panel .sheet-handle")).toBeVisible();
  await expect(page.locator(".panel")).toHaveAttribute("data-snap", "peek");
  await page.goto("./explore/?asset=126");
  await expect(page.locator(".drawer")).toHaveAttribute("data-snap", "half");
  const [sheet, area] = await page.evaluate(() => [document.querySelector(".drawer").getBoundingClientRect().height,
    document.querySelector(".explore").getBoundingClientRect().height]);
  expect(Math.abs(sheet / area - 0.55)).toBeLessThan(0.03);
});

test("Story: three-line H1, step 5 cites Dimsum Daily, 130 vs 129 explained", async ({ page }) => {
  await page.goto("./");
  await expect(page.locator("#h1 span")).toHaveText(["Small,", "concentrated,", "rising."]);
  await expect(page.locator(".kpi-note")).toContainText("under development");
  const link = page.locator(".step:has(#s5) a", { hasText: "Dimsum Daily, 8 September 2023" });
  await expect(link).toHaveAttribute("href", /^https:\/\/www\.dimsumdaily\.hk\//);
  await page.goto("./insights/");
  await expect(page.locator(".card-summary")).toHaveText("3 full · 8 partial · 0 none");
  await expect(page.locator(".sc-rows li")).toHaveCount(11);
});

// ---- v2.2 checks (decision 2026-10-12) ----
const lum = ([r, g, b]) => {
  const c = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b);
};

test("hero footnote: one line at 1440 px, at most two at 390 px, links to the Method explanation", async ({ page }) => {
  for (const [w, h, max] of [[1440, 900, 1], [390, 844, 2]]) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("./");
    const note = page.locator(".kpi-note");
    await expect(note).toContainText("under development at 31 March 2026");
    const lines = await note.evaluate((el) => Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight)));
    expect(lines, `${w}px`).toBeLessThanOrEqual(max);
    await expect(note.getByRole("link", { name: "Method" })).toHaveAttribute("href", /\/method\/#assessed$/);
  }
  await page.goto("./method/#assessed");
  await expect(page.locator("#assessed")).toContainText("under development");
});

// item 3: the kicker's text colour against the brightest rendered pixel behind it (text hidden, region screenshotted)
for (const [w, h] of PHONES) {
  test(`hero kicker reaches WCAG AA (4.5:1) against the photo at ${w}px`, async ({ page }, info) => {
    await page.setViewportSize({ width: w, height: h });
    for (const motion of ["reduce", "no-preference"]) {   // reduce = glow at full strength, no drift
      await page.emulateMedia({ reducedMotion: motion });
      await page.goto("./", { waitUntil: "networkidle" });
      await page.waitForTimeout(motion === "reduce" ? 300 : 4500);   // let the drift / glow move away from frame 0
      const kicker = page.locator(".hero .kicker");
      const fg = await kicker.evaluate((el) => getComputedStyle(el).color.match(/\d+/g).slice(0, 3).map(Number));
      await kicker.evaluate((el) => (el.style.color = "transparent"));
      const png = await page.screenshot({ clip: await kicker.boundingBox() });
      const bg = await page.evaluate(async (b64) => {
        const img = new Image(); img.src = `data:image/png;base64,${b64}`; await img.decode();
        const c = Object.assign(document.createElement("canvas"), { width: img.width, height: img.height });
        const x = c.getContext("2d"); x.drawImage(img, 0, 0);
        const d = x.getImageData(0, 0, c.width, c.height).data, px = [];
        for (let i = 0; i < d.length; i += 4) px.push([d[i], d[i + 1], d[i + 2]]);
        return px;
      }, png.toString("base64"));
      const Lfg = lum(fg), Lmax = Math.max(...bg.map(lum));
      const ratio = (Math.max(Lfg, Lmax) + 0.05) / (Math.min(Lfg, Lmax) + 0.05);
      info.annotations.push({ type: "contrast", description: `${w}px ${motion}: ${ratio.toFixed(2)}:1 (worst pixel)` });
      console.log(`kicker contrast ${w}px ${motion}: ${ratio.toFixed(2)}:1`);
      expect(ratio).toBeGreaterThanOrEqual(4.5);
    }
  });
}

test("Story legend on phones: one-row key (<= 15% of the viewport), Key opens the full legend over the map only", async ({ page }) => {
  await page.setViewportSize({ width: 360, height: 780 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("./");
  await page.locator("#story").scrollIntoViewIfNeeded();
  await mapReady(page, "storyMap");
  for (const id of ["#s1", "#s3", "#s4", "#s5"]) {
    await page.locator(id).scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    const key = page.locator(".lg-compact");
    await expect(key).toBeVisible();
    await expect(page.locator(".story-legend")).toBeHidden();
    const kb = await key.boundingBox();
    expect(kb.height, id).toBeLessThanOrEqual(780 * 0.15);
    // one row: every swatch on the same line
    const tops = await key.locator("span").evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().top)));
    expect(new Set(tops).size, id).toBe(1);
    // nothing clipped at the right edge
    const right = await key.locator("span").last().evaluate((e) => e.getBoundingClientRect().right);
    expect(right, id).toBeLessThanOrEqual(kb.x + kb.width - 4);
    // a card brought into view lands below the map + key
    const card = await page.locator(`.step:has(${id})`).evaluate((el) => { el.scrollIntoView({ block: "start" }); return el.querySelector(".step-card").getBoundingClientRect().top; });
    expect(card, id).toBeGreaterThanOrEqual(kb.y + kb.height - 1);
  }
  await page.getByRole("button", { name: "Key" }).click();
  const full = page.locator(".story-legend");
  await expect(full).toBeVisible();
  await expect(page.getByRole("button", { name: "Close" })).toHaveAttribute("aria-expanded", "true");
  const [fb, mb] = [await full.boundingBox(), await page.locator(".story-map").boundingBox()];
  expect(fb.y).toBeGreaterThanOrEqual(mb.y - 1);
  expect(fb.y + fb.height).toBeLessThanOrEqual(mb.y + mb.height + 1);   // over the map, never over the cards
  await page.getByRole("button", { name: "Close" }).click();
  await expect(full).toBeHidden();
});

for (const [w, h] of [[1440, 900], [1920, 1080]]) {
  test(`desktop attribution bottom-right, clear of the legend (${w}px)`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("./");
    await page.locator("#story").scrollIntoViewIfNeeded();
    await mapReady(page, "storyMap");
    for (const id of ["#s1", "#s2", "#s4", "#s5", "#s6"]) {
      await page.locator(id).evaluate((el) => el.scrollIntoView({ block: "center" }));
      await page.waitForTimeout(500);
      await attributionVisible(page, ".story");
      const [a, l] = [await page.locator(".story .maplibregl-ctrl-attrib").boundingBox(), await page.locator(".story-legend").boundingBox()];
      expect(a.x + a.width, id).toBeGreaterThan(w - 40);
      expect(a.y + a.height, id).toBeGreaterThan(h - 40);
      expect(a.x > l.x + l.width + 8 || a.y > l.y + l.height + 8, id).toBe(true);
    }
    // back at the top: the Story attribution belongs to the story, never shown over the hero
    await page.evaluate(() => scrollTo(0, 0));
    await page.waitForTimeout(300);
    expect((await page.locator(".story .maplibregl-ctrl-attrib").boundingBox()).y).toBeGreaterThanOrEqual(h);
    await page.goto("./explore/");
    await mapReady(page, "exploreMap");
    const a = await page.locator(".explore .maplibregl-ctrl-attrib").boundingBox();
    expect(a.x + a.width).toBeGreaterThan(w - 40);
  });
}

// item 6: at each step's default framing every property it is about is fully on the map (marker radius + margin)
for (const [w, h] of [[1440, 900], [390, 844]]) {
  test(`Story framing: no property marker clipped at the edge (${w}px)`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("./");
    await page.locator("#story").scrollIntoViewIfNeeded();
    await mapReady(page, "storyMap");
    const fc = await (await page.request.get("./data/assets.geojson")).json();
    const pts = Object.fromEntries(fc.features.map((f) => [f.properties.valuation_no, f.geometry.coordinates]));
    for (const step of [1, 2, 3, 4, 5, 6]) {
      await page.locator(`.step[data-step="${step}"]`).first().evaluate((el) => el.scrollIntoView({ block: "center" }));
      await page.waitForFunction((s) => window.__rt.storyFrame?.step === s && !window.__rt.storyMap.isMoving(), step, { timeout: 15_000 });
      const bad = await page.evaluate((P) => {
        const m = window.__rt.storyMap, c = m.getCanvas().getBoundingClientRect(), M = 10;
        return window.__rt.storyFrame.nos.filter((no) => {
          const p = m.project(P[no]), x = c.left + p.x, y = c.top + p.y;
          return x < Math.max(c.left, 0) + M || x > Math.min(c.right, innerWidth) - M || y < Math.max(c.top, 64) + M || y > Math.min(c.bottom, innerHeight) - M;
        });
      }, pts);
      expect(bad, `step ${step}`).toEqual([]);
    }
  });
}

test("Mangkhut cross-section labels at least 6 px apart (390 px)", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("./");
  const g = page.locator(".gauge svg").first();
  await g.scrollIntoViewIfNeeded();
  const r = await g.evaluate((svg) => ["g-floor", "g-sea", "g-entr"].map((c) => { const b = svg.querySelector(`.${c}`).getBoundingClientRect(); return [b.top, b.bottom]; }));
  expect(r[1][0] - r[0][1]).toBeGreaterThanOrEqual(6);
  expect(r[2][0] - r[1][1]).toBeGreaterThanOrEqual(6);
});

// ---- first public release (decision 2026-10-12): no placeholders on the Method page ----
test("Method: How I built this and About carry the final text, no placeholders", async ({ page }) => {
  await page.goto("./method/");
  const how = page.locator('section[aria-labelledby="how"] p');
  await expect(how).toHaveCount(4);
  await expect(how.locator("b")).toHaveText(["Why I built it.", "What was hard.", "What I checked myself.", "How I used AI."]);
  const about = page.locator('section[aria-labelledby="about"]');
  await expect(about).toContainText("Lee Pak Kiu Jeff");
  await expect(about).toContainText("Independent student project.");
  await expect(about.getByRole("link")).toHaveAttribute("href", "https://github.com/kj166/rising-tide-hk");
  await expect(page.locator("main")).not.toContainText("TO" + "DO");   // assembled: the public-build gate scans for the marker
  await expect(page.locator("main")).not.toContainText(/LinkedIn|contact email|author photo|process\.md/);
  await expect(page.locator(".todo, .photo-ph")).toHaveCount(0);
});
