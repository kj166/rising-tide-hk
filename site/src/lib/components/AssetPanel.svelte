<script>
  import { onMount } from "svelte";
  import { base } from "$app/paths";
  import { CLASS3, COLORS, SCENARIOS, SHORT, rpClass, rpColor } from "$lib/data.js";
  import { hkdRange, rpText, cleanName } from "$lib/format.js";
  import { marginSentence } from "$lib/copy.js";
  import { SHOW_LANDSD_AERIAL } from "$lib/config.js";

  // Asset detail: badges, return period by scenario chart, loss / break-even (top-10 only), margin note, aerial view
  let { p, coords, scenario, adapt, margin, footprints, ml, discount, horizon, onclose } = $props();
  const IMAGERY = "https://mapapi.geodata.gov.hk/gs/api/v1.0.0/xyz/imagery/WGS84/{z}/{x}/{y}.png";
  const d = $derived(p.scenarios[scenario]);
  const cls = $derived(rpClass(d.rp));
  let chartEl, satEl, heading;
  let sat;

  async function chart() {
    if (!chartEl) return;
    const Plot = await import("@observablehq/plot");
    const NONE = 400;
    const rows = SCENARIOS.map((s) => {
      const x = p.scenarios[s];
      return { s: SHORT[s], rp: x.rp ?? NONE, lo: x.rp_range[0] ?? NONE, hi: x.rp_range[1] ?? NONE, c: rpColor(x.rp), none: x.rp == null };
    });
    const node = Plot.plot({
      width: Math.min(372, chartEl.clientWidth || 340), height: 160, marginLeft: 108, marginRight: 16, marginTop: 8, marginBottom: 36,
      style: { fontFamily: "Inter, sans-serif", fontSize: "11px", color: COLORS.navy, background: "transparent" },
      x: { type: "log", domain: [1.6, 560], ticks: [2, 5, 10, 20, 50, 100, 200, NONE], tickFormat: (v) => (v === NONE ? "none" : v), label: "1 in N years →", labelAnchor: "right", grid: true },
      y: { domain: rows.map((r) => r.s), label: null, tickSize: 0 },
      marks: [
        Plot.ruleY(rows, { ariaHidden: true, y: "s", x1: "lo", x2: "hi", stroke: COLORS.navy, strokeWidth: 2 }),
        Plot.dot(rows, { ariaHidden: true, y: "s", x: "rp", r: 6, fill: (r) => (r.none ? COLORS.paper : r.c), stroke: COLORS.navy, strokeWidth: 1.5 }),
      ],
      ariaLabel: `Most frequent flooding sea level by scenario for ${cleanName(p.name)}`,
      ariaDescription: rows.map((r) => `${r.s}: ${r.none ? "not reached within 200 years" : `1-in-${r.rp} years`}`).join("; "),
    });
    node.querySelectorAll("g[aria-label]").forEach((g) => g.removeAttribute("aria-label"));
    chartEl.replaceChildren(node);
  }
  function aerial() {
    if (!SHOW_LANDSD_AERIAL || !satEl || !ml) return;
    sat?.remove();
    sat = new ml.Map({ container: satEl, interactive: false, attributionControl: false, center: coords, zoom: 17.3,
      canvasContextAttributes: { preserveDrawingBuffer: true },
      style: { version: 8, sources: { img: { type: "raster", tiles: [IMAGERY], tileSize: 256, maxzoom: 20 }, fp: { type: "geojson", data: footprints } },
        layers: [{ id: "img", type: "raster", source: "img" },
          { id: "fp", type: "line", source: "fp", filter: ["==", ["get", "valuation_no"], p.valuation_no], paint: { "line-color": COLORS.r1, "line-width": 2.5 } }] } });
  }
  $effect(() => { p; scenario; chart(); });
  $effect(() => { p; ml; aerial(); });
  onMount(() => { heading?.focus(); return () => sat?.remove(); });
  let copied = $state(false);
</script>

<div class="drawer-inner">
  <div class="d-head">
    <div><h2 id="d-name" tabindex="-1" bind:this={heading}>{cleanName(p.name)}</h2><p class="d-sub">No. {p.valuation_no} · {p.district || "District not recorded"}</p></div>
    <button class="close" onclick={onclose} aria-label="Close property details">✕</button>
  </div>
  <div class="badges">
    {#if d.tier_absolute}<span class="badge tier">{d.tier_absolute} · composite risk</span>{/if}
    {#each d.watch as w}<span class="badge watch">Asset to watch: {w}</span>{/each}
    <span class="badge {cls === 'none' ? '' : cls}">{cls === "none" ? "Coastal: not reached within 200 years" : `Coastal: ${rpText(d.rp)} sea level`}</span>
    {#if d.rp != null && !d.has_coastal_loss}<span class="badge">Water reaches the site but stops below the floor</span>{/if}
    <span class="badge"><i style="background:{CLASS3[p.rain_class]}"></i>Rain: {p.rain_class}{p.rain_band !== "other" ? ` (${p.rain_band})` : ""}</span>
    <span class="badge"><i style="background:{CLASS3[p.landslide_class]}"></i>Landslide: {p.landslide_class}</span>
    {#if p.location_approximate}<span class="badge">Approximate location</span>{/if}
  </div>
  <section class="d-sec"><h3>How often the sea reaches it</h3><div class="rp-chart" bind:this={chartEl}></div>
    <p class="source">Dot: the most frequent sea level (1-in-N years) that reaches the site; line: range for ±0.15 m ground-level uncertainty.</p></section>
  {#if margin}<section class="d-sec"><h3>Margin</h3><p class="margin-note">{marginSentence(margin)}</p></section>{/if}
  {#if adapt}
    <section class="d-sec stat-sec"><p class="stat num">{hkdRange(adapt.eal_hkd)}</p>
      <p class="stat-lbl">expected coastal flood loss a year · {SHORT.ssp245_2050}</p></section>
    <section class="d-sec"><h3>What a flood barrier is worth</h3>
      <p>A <b>0.5 m</b> barrier pays for itself if it costs less than <b class="num">{hkdRange(adapt.barriers["0.5"].central_hkd)}</b> over {horizon} years
        (up to <span class="num">{hkdRange(adapt.barriers["0.5"].upper_hkd)}</span> if 2050 conditions held throughout). A 1.0 m barrier: <span class="num">{hkdRange(adapt.barriers["1"].central_hkd)}</span>.</p>
      <p class="source">Break-even budget: avoided loss discounted at {discount * 100}% over {horizon} years. No Hong Kong barrier costs were found.</p></section>
  {:else}
    <section class="d-sec"><h3>Expected coastal flood loss · {SHORT[scenario]}</h3>
      <p>{d.has_coastal_loss ? "Some modelled damage. Not among the 10 largest coastal risks, so shown only as part of the portfolio total."
        : d.rp != null ? "None: water reaches the site but stops below the floor, so the model finds no damage."
        : "None within the 1-in-200-year event."}</p></section>
  {/if}
  <div class="share"><button class="btn ghost" onclick={() => { navigator.clipboard?.writeText(location.href); copied = true; }}>{copied ? "Link copied" : "Copy link to this view"}</button></div>
</div>
