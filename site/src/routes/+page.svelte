<script>
  import { onMount } from "svelte";
  import { base } from "$app/paths";
  import Seo from "$lib/components/Seo.svelte";
  import Photo from "$lib/components/Photo.svelte";
  import Gauge from "$lib/components/Gauge.svelte";
  import { COLORS, RP_CLASSES, flattenAssets, getJSON, rpColorExpr } from "$lib/data.js";
  import { hkdRange, pctRange, cleanName } from "$lib/format.js";
  import { marginSentence, subhead } from "$lib/copy.js";
  import { HK_BOUNDS, OFM_STYLE, attribution, loadMapLibre, themeLight } from "$lib/map.js";

  let { data } = $props();
  const P = data.portfolio, S = P.scenarios, F = S.ssp245_2050, B = S.baseline;
  const A = data.adaptation, M = data.meta.method;
  const quay = data.margins.assets[0];
  const ev = data.margins.events[0];
  const item11 = data.scorecard.items.find((i) => i.item === 11);
  const rainFirst = F.assets_to_watch.rain ?? [];
  // confirmed scorecard item 11 wording (exported): first clause and the adaptation caveat
  const [s11a, s11b] = item11.justification.split(/(?<=[\w)])\. (?=[A-Z])/);
  const linkTier = s11a.split(";")[0];
  const linkCaveat = `${s11b}.`;
  const PH = data.photos;
  const hero = PH.wm3_victoria_harbour_sunrise;
  const heroSrcset = hero.srcset_webp.split(", ").map((s) => `${base}/${s}`).join(", ");

  const kpis = [
    { v: P.n_assets_total, fmt: (x) => String(Math.round(x)), lbl: "Hong Kong properties mapped" },
    { v: F.n_assets_with_coastal_loss, fmt: (x) => String(Math.round(x)), lbl: `with modelled coastal flood damage by 2050 (SSP2-4.5), up from ${B.n_assets_with_coastal_loss}` },
    { v: 1, fmt: (e) => pctRange(F.top3_share_pct.map((x) => x * e)), final: pctRange(F.top3_share_pct), lbl: "of that risk sits in just three properties" },
    { v: 1, fmt: (e) => hkdRange(F.eal_total_hkd.map((x) => Math.max(1e6, x * e))), final: hkdRange(F.eal_total_hkd), lbl: `expected coastal flood loss a year by 2050, from ${hkdRange(B.eal_total_hkd)}` },
  ];
  // 130 vs 129 (pipeline: valuation status 'under_development' at 31 March 2026, config valuation.under_development_valuation_nos;
  // no built floor area or rental income, so no replacement cost, and excluded from damage and business interruption)
  const devNames = P.under_development_names.map(cleanName).join(", ");
  const WORDS = ["No site was", "One site was", "Two sites were", "Three sites were"];
  const devCount = WORDS[P.under_development_names.length] ?? `${P.under_development_names.length} sites were`;
  const DIMSUM = "https://www.dimsumdaily.hk/wong-tai-sin-district-severely-ravaged-by-black-rainstorm-warning-signal-temple-mall-north-submerged-in-floodwater/";
  let shown = $state(kpis.map((k) => k.final ?? k.fmt(k.v)));

  let storyEl, mapEl, attribSlot;
  let active = $state(1);
  let mapReady = $state(false);
  let keyOpen = $state(false);
  // short return-period labels for the one-row phone key ("1 in ≤10 · 20–50 · 100 · 200"); full wording in the Key panel
  const RP_SHORT = { r4: "≤10", r3: "20–50", r2: "100", r1: "200" };
  const reduce = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  onMount(() => {
    // KPI count-up (skipped under reduced motion; final values are in the prerendered HTML)
    if (!reduce()) {
      const t0 = performance.now();
      const tick = (t) => {
        const k = Math.min(1, (t - t0) / 1600), e = 1 - Math.pow(1 - k, 3);
        shown = kpis.map((x) => (k < 1 ? x.fmt(x.v * e) : x.final ?? x.fmt(x.v)));
        if (k < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }
    // lazy map + scroll steps when the story is near
    let scroller, map, cleanup = [];
    const io = new IntersectionObserver(async ([e]) => {
      if (!e.isIntersecting) return;
      io.disconnect();
      const [maplibregl, { default: scrollama }, assetsFC, fps] = await Promise.all([
        loadMapLibre(), import("scrollama"), getJSON(fetch, "assets.geojson"), getJSON(fetch, "footprints.geojson")]);
      const assets = flattenAssets(assetsFC);
      const byNo = new Map(assets.features.map((f) => [f.properties.valuation_no, f]));
      const byName = new Map(assets.features.map((f) => [f.properties.name, f]));
      map = new maplibregl.Map({ container: mapEl, style: OFM_STYLE, bounds: HK_BOUNDS, scrollZoom: false, dragRotate: false,
        attributionControl: false, canvasContextAttributes: { preserveDrawingBuffer: true } });
      // compact attribution. Desktop: bottom-right, moved into a sticky slot above the cards' layer (the map sits below the
      // cards, so a control left inside it would be crossed by them); the legend stays bottom-left. Phones: bottom-left of
      // the map (cards scroll below the map there, the key sits under it).
      if (innerWidth >= 900) {
        attribution(maplibregl, map, "bottom-right");
        attribSlot.append(mapEl.querySelector(".maplibregl-ctrl-bottom-right"));
      } else attribution(maplibregl, map, "bottom-left");
      window.__rt = { ...(window.__rt ?? {}), storyMap: map };
      const TOP3 = F.top3_valuation_nos, QUAY = quay.valuation_no, CW = ev.valuation_no;
      const rain = rainFirst.map((n) => byName.get(n)?.properties.valuation_no).filter(Boolean);
      const labels = [...TOP3, QUAY].map((no) => {
        const el = document.createElement("div");
        el.className = `map-label${no === QUAY ? " alt" : ""}`;
        el.textContent = cleanName(byNo.get(no).properties.name).replace(" Car Service Centre", " CSC");
        return [no, new maplibregl.Marker({ element: el, anchor: "left", offset: [10, 0] }).setLngLat(byNo.get(no).geometry.coordinates)];
      });
      const rainLabels = rain.map((no) => {
        const el = document.createElement("div");
        el.className = "map-label";
        el.textContent = cleanName(byNo.get(no).properties.name);
        return new maplibregl.Marker({ element: el, anchor: "left", offset: [10, 0] }).setLngLat(byNo.get(no).geometry.coordinates);
      });
      map.on("load", () => {
        themeLight(map);
        map.addSource("assets", { type: "geojson", data: assets });
        map.addSource("fp", { type: "geojson", data: fps });
        map.addLayer({ id: "fp-focus", type: "fill", source: "fp", filter: ["==", ["get", "valuation_no"], -1], paint: { "fill-color": COLORS.r3, "fill-opacity": 0.5 } });
        map.addLayer({ id: "fp-line", type: "line", source: "fp", filter: ["==", ["get", "valuation_no"], -1], paint: { "line-color": COLORS.navy, "line-width": 2 } });
        map.addLayer({ id: "s-pts", type: "circle", source: "assets", paint: { "circle-color": COLORS.teal } });
        mapReady = true;
        go(active);
      });
      // desktop: cards on the right, legend bottom-left over the map; mobile: the map is never covered (cards scroll below it)
      const wide = () => innerWidth >= 900;
      const pad = () => (wide() ? { top: 90, bottom: 60, left: 300, right: 560 } : { top: 20, bottom: 20, left: 20, right: 20 });
      const dur = (ms) => (reduce() ? 0 : ms);
      const fit = (nos, maxZoom = 13) => {
        const c = nos.map((n) => byNo.get(n).geometry.coordinates);
        const b = c.reduce((bb, p) => bb.extend(p), new maplibregl.LngLatBounds(c[0], c[0]));
        // room for the legend (left), the cards and the name labels (right) so no property sits at an edge
        map.fitBounds(b, { padding: wide() ? { top: 110, bottom: 90, left: 320, right: 660 } : { top: 40, bottom: 40, left: 36, right: 140 },
          duration: dur(1800), maxZoom });
      };
      function style(n) {
        const P_ = (k, v) => map.setPaintProperty("s-pts", k, v);
        const approx = ["get", "location_approximate"];
        if (n <= 2) {
          P_("circle-radius", ["interpolate", ["linear"], ["zoom"], 9, 3.5, 14, 8]);
          P_("circle-color", ["case", approx, "rgba(0,0,0,0)", COLORS.teal]);
          P_("circle-stroke-color", ["case", approx, COLORS.teal, COLORS.paper]);
          P_("circle-stroke-width", ["case", approx, 2, 1]);
          P_("circle-opacity", 1); P_("circle-stroke-opacity", 1);
        } else if (n === 5) {
          const r = ["match", ["get", "rain_class"], "high", COLORS.r4, "medium", COLORS.r2, COLORS.r1];
          P_("circle-radius", ["case", ["in", ["get", "valuation_no"], ["literal", rain]], 9, 5]);
          P_("circle-color", r); P_("circle-stroke-color", COLORS.navy); P_("circle-stroke-width", 1);
          P_("circle-opacity", 1); P_("circle-stroke-opacity", 1);
        } else {
          const reached = [">", ["get", "rp_ssp245_2050"], 0], loss = ["get", "loss_ssp245_2050"];
          P_("circle-radius", ["case", loss, 7, reached, 6.5, 3]);
          P_("circle-color", ["case", loss, rpColorExpr("ssp245_2050"), reached, COLORS.paper, COLORS.none]);
          P_("circle-stroke-color", ["case", reached, COLORS.navy, COLORS.paper]);
          P_("circle-stroke-width", ["case", loss, 1.2, reached, 2.5, 0.5]);
          P_("circle-opacity", ["case", reached, 1, 0.35]); P_("circle-stroke-opacity", ["case", reached, 1, 0.35]);
        }
        const focus = n === 2 ? [CW] : n === 4 ? TOP3 : n === 5 ? rain : [-1];
        map.setFilter("fp-focus", ["in", ["get", "valuation_no"], ["literal", n === 4 ? [-1] : focus]]);
        map.setFilter("fp-line", ["in", ["get", "valuation_no"], ["literal", n === 4 ? [...TOP3, QUAY] : focus]]);
        labels.forEach(([, m]) => (n === 4 ? m.addTo(map) : m.remove()));
        rainLabels.forEach((m) => (n === 5 ? m.addTo(map) : m.remove()));
      }
      function go(n) {
        if (!mapReady) return;
        style(n);
        // which properties each step's default framing must show in full (checked by the Playwright clipping test)
        const all = assets.features.map((f) => f.properties.valuation_no);
        window.__rt.storyFrame = { step: n, nos: n === 2 ? [CW] : n === 4 ? [...TOP3, QUAY] : n === 5 ? rain.slice(0, 1) : all };
        if (n === 1 || n === 3 || n === 6) map.fitBounds(HK_BOUNDS, { padding: pad(), duration: dur(1800) });
        if (n === 2) map.flyTo({ center: byNo.get(CW).geometry.coordinates, zoom: 16.2, offset: [wide() ? -240 : 0, 0], duration: dur(2200) });
        if (n === 4) fit([...TOP3, QUAY]);
        if (n === 5 && rain.length) map.flyTo({ center: byNo.get(rain[0]).geometry.coordinates, zoom: 15.5, offset: [wide() ? -240 : 0, 0], duration: dur(2200) });
      }
      scroller = scrollama();
      scroller.setup({ step: ".step", offset: wide() ? 0.6 : 0.8 }).onStepEnter(({ element }) => { active = +element.dataset.step; go(active); });
      const rs = () => scroller.resize();
      addEventListener("resize", rs);
      cleanup.push(() => removeEventListener("resize", rs));
    }, { rootMargin: "0px 0px 10% 0px" });
    io.observe(storyEl);
    return () => { io.disconnect(); scroller?.destroy(); map?.remove(); cleanup.forEach((f) => f()); };
  });
</script>

<Seo title="Small, concentrated, rising" description={subhead(P)} />

<svelte:head>
  <link rel="preload" as="image" type="image/webp" imagesrcset={heroSrcset} imagesizes="100vw" fetchpriority="high" />
</svelte:head>

<main id="main">
  <section class="hero on-navy" aria-labelledby="h1">
    <div class="hero-photo">
      <picture>
        <source type="image/webp" srcset={heroSrcset} sizes="100vw" />
        <img src="{base}/{hero.src}" width={hero.width} height={hero.height} alt={hero.alt} fetchpriority="high" decoding="async" />
      </picture>
    </div>
    <div class="hero-glow" aria-hidden="true"></div>
    <div class="hero-shade" aria-hidden="true"></div>
    <div class="hero-content">
      <p class="kicker">An independent study of Link REIT's Hong Kong portfolio</p>
      <h1 id="h1"><span>Small,</span> <span>concentrated,</span> <span>rising.</span></h1>
      <p class="subhead">{subhead(P)}</p>
      <ul class="kpis" aria-label="Key figures">
        {#each kpis as k, i}
          <li><span class="big" aria-label={k.final ?? k.fmt(k.v)}>{shown[i]}</span><span class="lbl">{k.lbl}</span></li>
        {/each}
      </ul>
      <p class="kpi-note">{P.n_assets_total} mapped; {P.n_assets} assessed. {devCount} still under development at 31 March 2026 (see <a href="{base}/method/#assessed">Method</a>).</p>
      <div class="hero-cta">
        <a class="btn primary" href="#story">Scroll the story <span aria-hidden="true">↓</span></a>
        <a class="btn ghost" href="{base}/explore/">Explore the map</a>
      </div>
    </div>
    <p class="hero-credit"><a href={hero.page}>{hero.credit}</a></p>
  </section>

  <section id="story" class="story" aria-label="Story" bind:this={storyEl}>
    <div class="story-map-wrap">
      <div class="story-map" bind:this={mapEl} role="img" aria-label="Map that follows the story: Link's Hong Kong properties, coloured by the step's measure.">
        {#if !mapReady}<div class="map-skeleton">Map loading…</div>{/if}
      </div>
      <!-- phones (< 640 px): a one-row key under the map; "Key" opens the full legend over the map (never over the cards) -->
      <div class="lg-compact" aria-hidden="true">
        {#if active <= 2}
          <span><i style="background:{COLORS.teal};border-color:{COLORS.paper}"></i>Matched</span>
          <span><i class="hollow" style="border-color:{COLORS.teal}"></i>Approx.</span>
          {#if active === 2}<span><i class="sq" style="background:{COLORS.r3}"></i>Footprint</span>{/if}
        {:else if active === 5}
          <span class="lc-t">Rain</span>
          <span><i style="background:{COLORS.r4}"></i>High</span><span><i style="background:{COLORS.r2}"></i>Med.</span><span><i style="background:{COLORS.r1}"></i>Low</span>
          <span><i class="sq" style="background:{COLORS.r3}"></i>Footprint</span>
        {:else}
          <span class="lc-t">1 in</span>
          {#each RP_CLASSES as c}<span><i style="background:{c.color}"></i>{RP_SHORT[c.key]}</span>{/each}
          <span><i class="hollow" style="border-color:{COLORS.navy}"></i>Reached</span>
          <span><i style="background:{COLORS.none};opacity:.4"></i>None</span>
        {/if}
      </div>
      <button class="lg-toggle" type="button" aria-expanded={keyOpen} aria-controls="story-legend" onclick={() => (keyOpen = !keyOpen)}>{keyOpen ? "Close" : "Key"}</button>
      <div class="story-legend legend" class:open={keyOpen} id="story-legend" aria-label="Map legend">
        {#if active <= 2}
          <div><i style="background:{COLORS.teal};border-color:{COLORS.paper}"></i>Property (footprint matched)</div>
          <div><i class="hollow" style="border-color:{COLORS.teal}"></i>Approximate location</div>
          {#if active === 2}<div><i class="sq" style="background:{COLORS.r3}"></i>Building footprint: {cleanName(ev.name)}</div>{/if}
        {:else if active === 5}
          <p class="lg-t">Rain-flood indicator (screening)</p>
          <div><i style="background:{COLORS.r4}"></i>High</div><div><i style="background:{COLORS.r2}"></i>Medium</div><div><i style="background:{COLORS.r1}"></i>Low</div>
          <div><i class="sq" style="background:{COLORS.r3}"></i>Building footprint: {rainFirst.map(cleanName).join(", ")}</div>
        {:else}
          <p class="lg-t">2050, SSP2-4.5 · properties with damage, by how often the sea reaches them</p>
          {#each RP_CLASSES as c}<div><i style="background:{c.color}"></i>{c.label}</div>{/each}
          <div><i class="hollow" style="border-color:{COLORS.navy}"></i>Water reaches, no damage</div>
          <div><i style="background:{COLORS.none};opacity:.4"></i>Not reached within 200 years</div>
          {#if active === 4}<div><i class="sq outline"></i>Building footprint</div><div><span class="lg-pill">Name</span>Three largest risks</div><div><span class="lg-pill alt">Name</span>Margin example</div>{/if}
        {/if}
      </div>
    </div>
    <div class="steps">
      <article class="step" class:is-active={active === 1} data-step="1" aria-labelledby="s1">
        <div class="step-card"><p class="step-no">1 / 6</p>
          <h2 id="s1"><span class="num">{P.n_assets_total}</span> properties</h2>
          <p>Link REIT's Hong Kong portfolio, from neighbourhood shopping centres to car parks. <strong class="num">{P.n_footprints}</strong> are matched to building footprints; <strong class="num">{M.n_location_approximate}</strong> are placed approximately (hollow dots).</p>
          <p>{devNames} is still under development, so <strong class="num">{P.n_assets}</strong> are assessed for flood loss.</p>
          <p class="source">Footprints: Lands Department iB1000 via CSDI Portal. Locations: our geocoding with manual checks.</p>
        </div>
      </article>
      <article class="step" class:is-active={active === 2} data-step="2" aria-labelledby="s2">
        <div class="step-card"><p class="step-no">2 / 6</p>
          <h2 id="s2">Typhoon Mangkhut, September 2018</h2>
          <p>The Hong Kong Observatory recorded a sea level of <strong class="num">{ev.observed_peak_mcd} m</strong> above Chart Datum at {ev.gauge_name}, the tide station our model uses for <strong>{cleanName(ev.name)}</strong>.</p>
          <p>Replayed there, the water rises <strong class="num">{ev.above_entry_cm} cm</strong> above the entrance but stops <strong class="num">{ev.below_floor_cm} cm</strong> below the lowest floor. Modelled loss: <strong class="num">{hkdRange([P.mangkhut_modelled_loss_hkd, P.mangkhut_modelled_loss_hkd])}</strong>.</p>
          <p class="source">Sea level: {ev.peak_source}. Site levels: our model on CEDD 2020 LiDAR.</p>
        </div>
      </article>
      <article class="step" class:is-active={active === 2} data-step="2" aria-label="Typhoon Mangkhut, continued">
        <div class="step-card"><p class="step-no">2 / 6 · continued</p>
          <Gauge aboveCm={ev.above_entry_cm} belowCm={ev.below_floor_cm} name={cleanName(ev.name)} />
          <p>A few centimetres separate no loss from a large one, so every result here is a range.</p>
          <Photo photo={PH.wm4_heng_fa_chuen_harbourfront_mangkhut} crop />
        </div>
      </article>
      <article class="step" class:is-active={active === 3} data-step="3" aria-labelledby="s3">
        <div class="step-card"><p class="step-no">3 / 6</p>
          <h2 id="s3">2050: <span class="num">{F.n_assets_with_coastal_loss}</span> properties take damage</h2>
          <p>By 2050 (SSP2-4.5, a middle-of-the-road scenario) a 1-in-200-year sea level or a more frequent one reaches <strong class="num">{F.n_assets_reached}</strong> properties, up from <span class="num">{B.n_assets_reached}</span>. At <strong class="num">{F.n_assets_with_coastal_loss}</strong> of them water gets inside, up from <span class="num">{B.n_assets_with_coastal_loss}</span> in the 1995–2014 climate.</p>
          {#if F.reached_no_loss_names.length}<p>At {F.reached_no_loss_names.map(cleanName).join(" and ")} it stops below the floor (hollow ring).</p>{/if}
          <p class="source">Our model: still-water coastal flooding, median sea-level rise (HKO), Port Works Design Manual extreme sea levels.</p>
        </div>
      </article>
      <article class="step" class:is-active={active === 4} data-step="4" aria-labelledby="s4">
        <div class="step-card"><p class="step-no">4 / 6</p>
          <h2 id="s4">Three properties carry <span class="num">{pctRange(F.top3_share_pct)}</span> of the risk</h2>
          <p><strong>{F.top3_names.map(cleanName).slice(0, -1).join(", ")}</strong> and <strong>{cleanName(F.top3_names.at(-1))}</strong> carry {pctRange(F.top3_share_pct)} of the portfolio's 2050 coastal flood risk. The other {F.n_assets_with_coastal_loss - F.top3_names.length} properties with damage share the rest.</p>
          <p class="source">Shares: expected annual loss at mid replacement cost, with and without events rarer than 1-in-200 years.</p>
        </div>
      </article>
      <article class="step" class:is-active={active === 4} data-step="4" aria-label="Margins, continued">
        <div class="step-card"><p class="step-no">4 / 6 · continued</p>
          <p class="margin-note">{marginSentence(quay)}</p>
          <p class="source">Margins: our model on CEDD 2020 LiDAR and HKO's likely range. Value rank: Link valuation report, 31 March 2026.</p>
          <Photo photo={PH.wm1_chai_wan_cargo_handling_basin} crop />
        </div>
      </article>
      <article class="step" class:is-active={active === 5} data-step="5" aria-labelledby="s5">
        <div class="step-card"><p class="step-no">5 / 6</p>
          <h2 id="s5">{rainFirst.map(cleanName).join(", ")} and the September 2023 rainstorm</h2>
          <p>Our rain-flood indicator puts <strong>{rainFirst.map(cleanName).join(", ")}</strong> first among Link's {P.n_assets_total} properties. During the black rainstorm of 7–8 September 2023, local media reported its ground floor submerged in floodwater.</p>
          <p>{linkTier}. {linkCaveat} The composite score hides single-hazard extremes like this, so we flag the top property on each hazard as an asset to watch.</p>
          <p class="source">Media report: <a href={DIMSUM}>Dimsum Daily, 8 September 2023</a>. Link's assessment: ESG Data Compendium 2025/26, p. 78. The rain indicator is a screening measure, not a probability.</p>
        </div>
      </article>
      <article class="step" class:is-active={active === 6} data-step="6" aria-labelledby="s6">
        <div class="step-card"><p class="step-no">6 / 6</p>
          <h2 id="s6">What it costs, and what barriers are worth</h2>
          <p>Expected coastal flood loss rises from <strong class="num">{hkdRange(B.eal_total_hkd)}</strong> a year in the 1995–2014 climate to <strong class="num">{hkdRange(F.eal_total_hkd)}</strong> by 2050: {F.share_of_net_income_pct[0]}–{F.share_of_net_income_pct[1]}% of Link's Hong Kong net income.</p>
          <p>A {M.barrier_heights_m[0].toFixed(1)} m flood barrier at the {A.assets.length} most exposed properties pays for itself at any cost below <strong class="num">{hkdRange(A.totals[String(M.barrier_heights_m[0])].central_hkd)}</strong> over {A.horizon_years} years ({A.discount_rate * 100}% a year). No Hong Kong barrier costs were found: these are budgets, not prices.</p>
          <div class="hero-cta" style="margin-top:var(--s-4)">
            <a class="btn primary" href="{base}/explore/">Explore every property</a>
            <a class="btn ghost" style="color:var(--navy)" href="{base}/insights/">See the insights</a>
          </div>
        </div>
      </article>
    </div>
    <div class="story-attrib-slot" bind:this={attribSlot}></div>
  </section>
</main>
