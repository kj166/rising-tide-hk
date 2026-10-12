<script>
  import * as Plot from "@observablehq/plot";
  import Seo from "$lib/components/Seo.svelte";
  import ChartCard from "$lib/components/ChartCard.svelte";
  import { COLORS, RP_CLASSES, SHORT, rpColor } from "$lib/data.js";
  import { hkdRange, pctRange, cleanName } from "$lib/format.js";
  import { ealSentence, marginSentence } from "$lib/copy.js";

  let { data } = $props();
  const P = data.portfolio, S = P.scenarios, F = S.ssp245_2050, B = S.baseline, A = data.adaptation, SC = data.scorecard, M = data.meta.method;
  const FONT = { fontFamily: "Inter, sans-serif", fontSize: "12px", color: COLORS.navy, background: "transparent" };
  const ALL = ["baseline", "ssp245_2050", "ssp585_2050", "ssp585_2100"];

  // Shared layout for horizontal range charts. Below 640 px each name sits above its bar, full width (no left margin to
  // clip); wider, names sit in the left margin. Category axes never draw tick marks (tickSize 0).
  const NARROW = 640;
  function layout(w, rows, key, left, rowWide = 26, rowNarrow = 46) {
    const narrow = w < NARROW;
    return {
      narrow,
      marginLeft: narrow ? 4 : Math.min(left, w * 0.45),
      height: (narrow ? rowNarrow : rowWide) * rows.length,
      y: { domain: rows.map((r) => r[key]), label: null, tickSize: 0, axis: narrow ? null : "left" },
      dy: narrow ? 8 : 0,
      names: narrow ? [Plot.text(rows, { ariaHidden: true, y: key, text: key, frameAnchor: "left", textAnchor: "start", dy: -12, fontWeight: 600, fontSize: 12 })] : [],
    };
  }

  // 1. expected annual loss by scenario (2100 is a sensitivity, off-scale note)
  const eal = ["baseline", "ssp245_2050", "ssp585_2050"].map((s) => ({ s: SHORT[s], lo: S[s].eal_total_hkd[0] / 1e6, hi: S[s].eal_total_hkd[1] / 1e6, txt: hkdRange(S[s].eal_total_hkd), base: s === "baseline" }));
  const makeEal = (w) => { const L = layout(w, eal, "s", 116, 50, 54); return Plot.plot({ width: w, height: L.height + 46, marginLeft: L.marginLeft, marginRight: 86, marginTop: 10, marginBottom: 36, style: FONT,
    x: { domain: [0, Math.max(...eal.map((d) => d.hi)) * 1.05], label: "HK$ million a year →", grid: true, labelAnchor: "left" }, y: L.y,
    marks: [...L.names, Plot.ruleY(eal, { ariaHidden: true, y: "s", x1: "lo", x2: "hi", dy: L.dy, stroke: (d) => (d.base ? COLORS.teal : COLORS.navy), strokeWidth: 12, strokeLinecap: "round" }),
      Plot.text(eal, { ariaHidden: true, y: "s", x: "hi", text: "txt", dy: L.dy, dx: 12, textAnchor: "start", fontWeight: 600, fontSize: 13 })],
    ariaLabel: "Range of expected annual coastal flood loss by scenario", ariaDescription: eal.map((d) => `${d.s}: ${d.txt}`).join("; ") }); };

  // 2. concentration: the ten largest coastal risks, the three largest highlighted
  const top3 = new Set(F.top3_valuation_nos);
  const t10 = A.assets.map((a) => ({ name: cleanName(a.name), lo: a.eal_hkd[0] / 1e6, hi: a.eal_hkd[1] / 1e6, txt: hkdRange(a.eal_hkd), top: top3.has(a.valuation_no) }))
    .sort((x, y) => (y.lo + y.hi) - (x.lo + x.hi));
  const makeConc = (w) => { const L = layout(w, t10, "name", 230); return Plot.plot({ width: w, height: L.height + 46, marginLeft: L.marginLeft, marginRight: 86, marginTop: 10, marginBottom: 36, style: FONT,
    x: { label: "Expected annual loss, 2050, HK$ million →", grid: true, labelAnchor: "left" }, y: L.y,
    marks: [...L.names, Plot.ruleY(t10, { ariaHidden: true, y: "name", x1: "lo", x2: "hi", dy: L.dy, stroke: (d) => (d.top ? COLORS.r3 : COLORS.inkMuted), strokeWidth: 9, strokeLinecap: "round" }),
      Plot.text(t10, { ariaHidden: true, y: "name", x: "hi", text: "txt", dy: L.dy, dx: 10, textAnchor: "start", fontSize: 11 })],
    ariaLabel: "Expected annual coastal flood loss of the ten largest coastal risks, 2050",
    ariaDescription: t10.map((d) => `${d.name}: ${d.txt}${d.top ? " (one of the three largest)" : ""}`).join("; ") }); };

  // 3. return period dumbbell, 1995–2014 → 2050; headline counts come from the export and must agree with the rows
  const NONE = 400;
  const rr = P.reached_rp.map((r) => ({ name: cleanName(r.name), b: r.baseline ?? NONE, f: r.ssp245_2050 ?? NONE, c: rpColor(r.ssp245_2050) }))
    .sort((x, y) => x.f - y.f || x.b - y.b || x.name.localeCompare(y.name));
  const nBase = rr.filter((r) => r.b !== NONE).length, nFut = rr.filter((r) => r.f !== NONE).length;
  if (nBase !== B.n_assets_reached || nFut !== F.n_assets_reached) throw new Error(`reached counts disagree: ${nBase}/${B.n_assets_reached}, ${nFut}/${F.n_assets_reached}`);
  const lab = (v) => (v === NONE ? "not within 200 years" : `1-in-${v}`);
  const makeDumb = (w) => { const L = layout(w, rr, "name", 270); return Plot.plot({ width: w, height: L.height + 60, marginLeft: L.marginLeft, marginRight: 20, marginTop: 10, marginBottom: 50, style: FONT,
    x: { type: "log", domain: [1.6, 560], ticks: [2, 5, 10, 20, 50, 100, 200, NONE], tickFormat: (v) => (v === NONE ? "none" : v), label: "Sea level that first reaches the property, 1 in N years (left = more often)", labelAnchor: "left", labelOffset: 40, grid: true },
    y: L.y,
    marks: [...L.names, Plot.link(rr, { ariaHidden: true, y1: "name", y2: "name", x1: "b", x2: "f", dy: L.dy, stroke: COLORS.inkMuted, strokeWidth: 1.5 }),
      Plot.dot(rr, { ariaHidden: true, y: "name", x: "b", dy: L.dy, r: 5, fill: COLORS.paper, stroke: COLORS.navy, strokeWidth: 1.5 }),
      Plot.dot(rr, { ariaHidden: true, y: "name", x: "f", dy: L.dy, r: 6, fill: "c", stroke: COLORS.navy, strokeWidth: 1.5 })],
    ariaLabel: "For each exposed property, the most frequent sea level that reaches it, 1995–2014 and 2050",
    ariaDescription: rr.map((r) => `${r.name}: ${lab(r.b)} to ${lab(r.f)}`).join("; ") }); };

  // 4. break-even budgets per property (0.5 m and 1.0 m barriers, central case)
  const [h1, h2] = M.barrier_heights_m.map(String);           // keys in adaptation.json ("0.5", "1")
  const [l1, l2] = M.barrier_heights_m.map((h) => `${h.toFixed(1)} m`);
  const be = A.assets.map((a) => ({ name: cleanName(a.name), b1: a.barriers[h1], b2: a.barriers[h2] }));
  const rows1 = be.map((d) => ({ name: d.name, lo: d.b1.central_hkd[0] / 1e6, hi: d.b1.central_hkd[1] / 1e6 }));
  const rows2 = be.map((d) => ({ name: d.name, lo: d.b2.central_hkd[0] / 1e6, hi: d.b2.central_hkd[1] / 1e6 }));
  const overtopped = be.filter((d) => d.b1.upper_hkd[1] === 0).map((d) => d.name);
  const makeBe = (w) => { const L = layout(w, be, "name", 250, 38, 54); return Plot.plot({ width: w, height: L.height + 46, marginLeft: L.marginLeft, marginRight: 20, marginTop: 10, marginBottom: 36, style: FONT,
    x: { label: `Break-even budget over ${A.horizon_years} years, HK$ million →`, grid: true, labelAnchor: "left" }, y: L.y,
    marks: [...L.names, Plot.ruleY(rows2, { ariaHidden: true, y: "name", x1: "lo", x2: "hi", stroke: COLORS.teal, strokeWidth: 7, strokeLinecap: "round", dy: L.dy + 4 }),
      Plot.ruleY(rows1, { ariaHidden: true, y: "name", x1: "lo", x2: "hi", stroke: COLORS.navy, strokeWidth: 7, strokeLinecap: "round", dy: L.dy - 4 })],
    ariaLabel: `Break-even budget ranges for ${l1} and ${l2} flood barriers at the ten largest coastal risks`,
    ariaDescription: be.map((d) => `${d.name}: ${l1} ${hkdRange(d.b1.central_hkd)}, ${l2} ${hkdRange(d.b2.central_hkd)}`).join("; ") }); };

  // 5. disclosure scorecard: one row per item, label left, a two-segment bar right (filled segment = 1 point)
  const nFull = SC.items.filter((i) => i.score === i.max_score).length;
  const nNone = SC.items.filter((i) => i.score === 0).length;
  const nPartial = SC.items.length - nFull - nNone;
  const makeSc = () => {
    const ol = document.createElement("ol");
    ol.className = "sc-rows";
    ol.setAttribute("aria-label", `Disclosure scorecard: ${SC.total} of ${SC.max} points`);
    for (const i of SC.items) {
      const li = document.createElement("li");
      const t = Object.assign(document.createElement("span"), { className: "sc-label", textContent: `${i.item}. ${i.title}` });
      const bar = Object.assign(document.createElement("span"), { className: "sc-bar" });
      bar.setAttribute("role", "img");
      bar.setAttribute("aria-label", `${i.score} of ${i.max_score}`);
      for (let k = 0; k < i.max_score; k++) bar.append(Object.assign(document.createElement("i"), { className: k < i.score ? "on" : "" }));
      li.append(t, bar);
      ol.append(li);
    }
    return ol;
  };
</script>

<Seo title="Insights" description={ealSentence(S)} path="/insights/" />

<main id="main">
  <header class="ins-head">
    <p class="eyebrow">Insights</p>
    <h1>What the numbers say</h1>
    <p class="lede">Each card makes one point. Switch to the table for the values, or download them. Every figure is a range: thresholds and assumptions matter more than any single number.</p>
  </header>
  <div id="cards" class="cards">
    <ChartCard id="eal" kicker="Expected annual loss · coastal flooding" title={ealSentence(S)} make={makeEal} label="Expected annual loss by scenario"
      table={{ cols: ["Scenario", "Expected annual loss", "Share of HK net income", "Properties with any loss"],
        rows: ALL.map((s) => [SHORT[s], hkdRange(S[s].eal_total_hkd), `${S[s].share_of_net_income_pct[0]}–${S[s].share_of_net_income_pct[1]}%`, S[s].n_assets_with_coastal_loss]),
        csv: ALL.map((s) => [SHORT[s], `${S[s].eal_total_hkd[0]}-${S[s].eal_total_hkd[1]} HKD`, `${S[s].share_of_net_income_pct[0]}-${S[s].share_of_net_income_pct[1]}%`, S[s].n_assets_with_coastal_loss]) }}
      source="Our model. Extreme sea levels: Port Works Design Manual (CEDD, 2022); sea-level rise: HKO; damage: JRC depth-damage curves; downtime: FEMA Hazus 7.0. Lower figure: events up to 1-in-200 years and half the Hazus restoration days; upper: rarer events and full days. Mid replacement cost.">
      {#snippet after()}<p class="off-scale"><span aria-hidden="true">→</span><span>{SHORT.ssp585_2100} (sensitivity, off this scale): <b>{hkdRange(S.ssp585_2100.eal_total_hkd)}</b> a year</span></p>{/snippet}
    </ChartCard>

    <ChartCard id="concentration" kicker="Concentration · 2050 (SSP2-4.5)" title="Three properties carry {pctRange(F.top3_share_pct)} of the 2050 coastal flood risk; {F.n_assets_with_coastal_loss} of {P.n_assets} carry any."
      make={makeConc} label="Ten largest coastal risks"
      table={{ cols: ["Property", "Expected annual loss, 2050", "Among the three largest"], rows: t10.map((d) => [d.name, d.txt, d.top ? "yes" : ""]),
        csv: A.assets.map((a) => [cleanName(a.name), `${a.eal_hkd[0]}-${a.eal_hkd[1]} HKD`, top3.has(a.valuation_no) ? "yes" : ""]) }}
      source="Our model. Coral: the three largest, the same on every basis. Per-property figures are published only for these ten. Shares at two significant figures.">
      {#snippet after()}{#each data.margins.assets as m}<p class="margin-note">{marginSentence(m)}</p>{/each}{/snippet}
    </ChartCard>

    <ChartCard id="dumbbell" kicker="Return period · 1995–2014 → 2050 (SSP2-4.5)" title="By 2050 the sea reaches {F.n_assets_reached} properties in a 1-in-200-year event or more often, up from {B.n_assets_reached}. At {F.n_assets_with_coastal_loss} of them, water gets inside."
      make={makeDumb} label="Return period dumbbell"
      table={{ cols: ["Property", "1995–2014 climate", "2050 (SSP2-4.5)"], rows: rr.map((r) => [r.name, lab(r.b), lab(r.f)]), csv: rr.map((r) => [r.name, lab(r.b), lab(r.f)]) }}
      source="Our model: still-water coastal flooding (no waves), median sea-level rise, ground levels from CEDD 2020 LiDAR. Water that reaches a property does not always damage it: the floor can sit higher than the entrance.">
      {#snippet after()}<div class="dots-legend" style="margin-top:8px"><span><i style="border:2px solid {COLORS.navy}"></i>1995–2014 climate</span>{#each RP_CLASSES as c}<span><i style="background:{c.color};border:1.5px solid {COLORS.navy}"></i>2050: {c.label}</span>{/each}</div>{/snippet}
    </ChartCard>

    <ChartCard id="breakeven" kicker="What a flood barrier is worth" title="A {l1} barrier at the {A.assets.length} most exposed properties pays for itself at any cost below {hkdRange(A.totals[h1].central_hkd)} over {A.horizon_years} years."
      make={makeBe} label="Break-even budgets"
      table={{ cols: ["Property", `${l1}, central`, `${l1}, 2050 held`, `${l2}, central`, `${l2}, 2050 held`],
        rows: be.map((d) => [d.name, hkdRange(d.b1.central_hkd), hkdRange(d.b1.upper_hkd), hkdRange(d.b2.central_hkd), hkdRange(d.b2.upper_hkd)]),
        csv: be.map((d) => [d.name, ...[d.b1.central_hkd, d.b1.upper_hkd, d.b2.central_hkd, d.b2.upper_hkd].map((r) => `${r[0]}-${r[1]} HKD`)]) }}
      source="Break-even budget: present value of the avoided expected annual loss (damage plus business interruption, mid replacement cost), {A.horizon_years} years at {A.discount_rate * 100}%. No Hong Kong barrier costs were found, so these are budgets, not prices.">
      {#snippet after()}<div class="dots-legend" style="margin-top:8px"><span><i style="background:{COLORS.navy}"></i>{l1} barrier</span><span><i style="background:{COLORS.teal}"></i>{l2} barrier</span></div>
        <p class="note">Central case: avoided loss rises from the 1995–2014 climate to 2050. If 2050 conditions held throughout, the ten together reach {hkdRange(A.totals[h1].upper_hkd)} ({l1}) and {hkdRange(A.totals[h2].upper_hkd)} ({l2}).{#if overtopped.length}{" "}At {overtopped.join(" and ")} a {l1} barrier is overtopped under 2050 conditions, so its value comes from the earlier years.{/if}</p>{/snippet}
    </ChartCard>

    <ChartCard id="scorecard" kicker="How Link discloses" title="Link's climate disclosure scores {SC.total} of {SC.max}: full marks on {nFull} of {SC.items.length} items."
      make={makeSc} label="Disclosure scorecard"
      table={{ cols: ["Item", "Score", "Evidence", "Why"], rows: SC.items.map((i) => [`${i.item}. ${i.title}`, `${i.score} / ${i.max_score}`, i.evidence, i.justification]),
        csv: SC.items.map((i) => [`${i.item}. ${i.title}`, `${i.score}/${i.max_score}`, i.evidence, i.justification]) }}
      summary="{nFull} full · {nPartial} partial · {nNone} none"
      source="Scored against the HKEX Appendix C2 climate disclosures that Link says its report follows (self-declared alignment), with TCFD and IFRS S2 as reference. A low score marks a gap in disclosure, not a breach of any rule." />
  </div>
</main>
