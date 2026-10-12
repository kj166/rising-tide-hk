<script>
  import { onMount } from "svelte";
  import Seo from "$lib/components/Seo.svelte";
  import AssetPanel from "$lib/components/AssetPanel.svelte";
  import Sheet from "$lib/components/Sheet.svelte";
  import { CLASS3, COLORS, RP_CLASSES, SCENARIOS, SCENARIO_NOTE, SHORT, dataUrl, flattenAssets, getJSON, rpColorExpr } from "$lib/data.js";
  import { hkdRange, cleanName } from "$lib/format.js";
  import { getQuery, setQuery } from "$lib/url.js";
  import { HK_BOUNDS, OFM_STYLE, add3dBuildings, addHillshade, attribution, loadMapLibre, themeLight } from "$lib/map.js";

  let { data } = $props();
  const H = data.heat, A = data.adaptation, M = data.meta.method;
  const HAZARDS = [["coastal", "Coastal"], ["rain", "Rain"], ["landslide", "Landslide"], ["heat", "Heat"]];
  const FILTERS = [["tier1", "Tier 1"], ["tier2", "Tier 2"], ["hotspot", `Hotspots (top ${M.hotspot_top_n})`], ["watch", "Assets to watch"]];
  const adaptBy = new Map(A.assets.map((a) => [a.valuation_no, a]));
  const marginBy = new Map(data.margins.assets.map((m) => [m.valuation_no, m]));

  // state (mirrored in the URL: scenario, asset, hazard, sea, compare, filter, view)
  let scenario = $state("ssp245_2050"), hazard = $state("coastal"), asset = $state(null);
  let sea = $state(null), compare = $state(false), filter = $state(null), view3d = $state(false), hlcOn = $state(false);
  let ready = $state(false), q = $state(""), activeOpt = $state(-1);
  let assets = $state(null), footprints = $state(null), ml = $state(null);
  let mapEl, mapBEl, map, mapB, extents, hlc;
  let swipeX = $state(50);
  let panelSnap = $state("peek"), drawerSnap = $state("half");

  const props = $derived(assets ? assets.features.map((f) => f.properties) : []);
  const selected = $derived(asset != null && assets ? assets.features.find((f) => f.properties.valuation_no === asset) : null);
  const hits = $derived(q.trim() ? props.filter((p) => `${p.name} ${p.district} ${p.valuation_no}`.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 8) : []);

  function colorExpr(s) {
    if (hazard === "rain") return ["match", ["get", "rain_class"], "low", CLASS3.low, "medium", CLASS3.medium, "high", CLASS3.high, COLORS.none];
    if (hazard === "landslide") return ["match", ["get", "landslide_class"], "low", CLASS3.low, "medium", CLASS3.medium, "high", CLASS3.high, COLORS.none];
    if (hazard === "heat") return COLORS.teal;
    return rpColorExpr(s);
  }
  function filterExpr(s) {
    if (filter === "tier1") return ["==", ["get", `tier_${s}`], "Tier 1"];
    if (filter === "tier2") return ["==", ["get", `tier_${s}`], "Tier 2"];
    if (filter === "hotspot") return ["==", ["get", `hot_${s}`], 1];
    if (filter === "watch") return ["==", ["get", `watch_${s}`], 1];
    return true;
  }
  function addLayers(m, s) {
    themeLight(m);
    addHillshade(m, data.meta, dataUrl, "water");
    add3dBuildings(m);
    m.addSource("ext", { type: "geojson", data: extents ?? { type: "FeatureCollection", features: [] } });
    m.addSource("fp", { type: "geojson", data: footprints });
    m.addSource("assets", { type: "geojson", data: assets });
    m.addLayer({ id: "ext", type: "fill", source: "ext", filter: ["==", ["get", "pass_m"], -1], paint: { "fill-color": COLORS.teal, "fill-opacity": 0.4 } });
    m.addLayer({ id: "ext-line", type: "line", source: "ext", filter: ["==", ["get", "pass_m"], -1], paint: { "line-color": COLORS.tealInk, "line-width": 0.8 } });
    m.addLayer({ id: "fp", type: "fill", source: "fp", minzoom: 13.5, paint: { "fill-color": COLORS.r3, "fill-opacity": 0.7 } });
    m.addLayer({ id: "fp-line", type: "line", source: "fp", minzoom: 13.5, paint: { "line-color": COLORS.navy, "line-width": 1 } });
    // selection: a matched footprint gets a thick navy outline; the ring is only for approximate locations (and for
    // matched ones when zoomed out below the footprint layers)
    m.addLayer({ id: "sel-fp", type: "line", source: "fp", minzoom: 13.5, filter: ["==", ["get", "valuation_no"], -1],
      paint: { "line-color": COLORS.navy, "line-width": 4.5 } });
    m.addLayer({ id: "sel", type: "circle", source: "assets", filter: ["==", ["get", "valuation_no"], -1],
      paint: { "circle-radius": 15, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": COLORS.navy, "circle-stroke-width": 3 } });
    m.addLayer({ id: "sel-lo", type: "circle", source: "assets", maxzoom: 13.5, filter: ["==", ["get", "valuation_no"], -1],
      paint: { "circle-radius": 15, "circle-color": "rgba(0,0,0,0)", "circle-stroke-color": COLORS.navy, "circle-stroke-width": 3 } });
    m.addLayer({ id: "pts", type: "circle", source: "assets", paint: {} });
    restyle(m, s);
  }
  function restyle(m, s) {
    if (!m?.getLayer("pts")) return;
    const c = colorExpr(s), approx = ["get", "location_approximate"], on = filterExpr(s);
    m.setPaintProperty("pts", "circle-color", ["case", approx, "rgba(0,0,0,0)", c]);
    m.setPaintProperty("pts", "circle-stroke-color", ["case", approx, c, COLORS.navy]);
    m.setPaintProperty("pts", "circle-stroke-width", ["case", approx, 2.2, ["==", ["get", `tier_${s}`], "Tier 1"], 2.4, 1]);
    m.setPaintProperty("pts", "circle-radius", ["interpolate", ["linear"], ["zoom"], 9, ["case", [">", ["get", `rp_${s}`], 0], 5.5, 3.5], 15, 9]);
    m.setPaintProperty("pts", "circle-opacity", ["case", on, 1, 0.15]);
    m.setPaintProperty("pts", "circle-stroke-opacity", ["case", on, 1, 0.15]);
    m.setPaintProperty("fp", "fill-color", ["match", ["get", "valuation_no"], ...props.flatMap((p) => [p.valuation_no, hazard === "coastal" ? (RP_CLASSES.find((k) => k.key === p[`rp_class_${s}`])?.color ?? COLORS.none) : (CLASS3[hazard === "rain" ? p.rain_class : p.landslide_class] ?? COLORS.teal)]), COLORS.none]);
    const lvl = hazard === "coastal" && sea ? sea : -1;
    m.setFilter("ext", ["==", ["get", "pass_m"], lvl]);
    m.setFilter("ext-line", ["==", ["get", "pass_m"], lvl]);
    const isSel = ["==", ["get", "valuation_no"], asset ?? -1];
    m.setFilter("sel", ["all", isSel, ["get", "location_approximate"]]);
    m.setFilter("sel-lo", ["all", isSel, ["!", ["get", "location_approximate"]]]);
    m.setFilter("sel-fp", isSel);
    if (m.getLayer("hlc")) m.setLayoutProperty("hlc", "visibility", hazard === "landslide" && hlcOn ? "visible" : "none");
  }
  async function ensureHlc() {
    if (hlc || !map) return;
    hlc = await getJSON(fetch, "hlc.geojson");
    map.addSource("hlc", { type: "geojson", data: hlc, attribution: "Historical Landslide Catchments: GEO, CEDD" });
    map.addLayer({ id: "hlc", type: "circle", source: "hlc", paint: { "circle-radius": 2, "circle-color": "#6B4E3D", "circle-opacity": 0.6 } }, "pts");
    restyle(map, scenario);
  }
  const drawerPad = () => (innerWidth >= 900 ? { left: 380, right: 420, top: 0, bottom: 0 } : { bottom: innerHeight * 0.5, top: 0, left: 0, right: 0 });
  function select(no, fly = true) {
    asset = no;
    drawerSnap = "half";
    const f = assets?.features.find((x) => x.properties.valuation_no === no);
    if (fly && f && map) map.flyTo({ center: f.geometry.coordinates, zoom: Math.max(map.getZoom(), 15), padding: drawerPad(),
      duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 1200 });
  }
  function pick(no) { q = ""; activeOpt = -1; select(no); }
  function searchKey(e) {
    if (!hits.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); activeOpt = (activeOpt + (e.key === "ArrowDown" ? 1 : -1) + hits.length) % hits.length; }
    else if (e.key === "Enter" && activeOpt >= 0) pick(hits[activeOpt].valuation_no);
    else if (e.key === "Escape") q = "";
  }
  function tabKey(e, i) {
    const k = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (!k) return;
    const n = HAZARDS[(i + k + HAZARDS.length) % HAZARDS.length][0];
    hazard = n;
    document.getElementById(`t-${n}`)?.focus();
  }
  function setX(v) { swipeX = Math.max(5, Math.min(95, v)); }
  function swipeDown(e) {
    const h = e.currentTarget;
    h.setPointerCapture(e.pointerId);
    const move = (ev) => setX((ev.clientX / innerWidth) * 100);
    h.addEventListener("pointermove", move);
    h.addEventListener("pointerup", () => h.removeEventListener("pointermove", move), { once: true });
  }

  onMount(async () => {
    const S = getQuery("scenario");
    if (SCENARIOS.includes(S)) scenario = S;
    const hz = getQuery("hazard");
    if (HAZARDS.some(([k]) => k === hz)) hazard = hz;
    asset = getQuery("asset") ? +getQuery("asset") : null;
    sea = getQuery("sea") ? +getQuery("sea") : null;
    compare = getQuery("compare") === "1";
    filter = FILTERS.some(([k]) => k === getQuery("filter")) ? getQuery("filter") : null;
    view3d = getQuery("view") === "3d";
    let fc;
    [ml, fc, footprints] = await Promise.all([loadMapLibre(), getJSON(fetch, "assets.geojson"), getJSON(fetch, "footprints.geojson")]);
    assets = flattenAssets(fc);
    const f0 = asset != null ? assets.features.find((f) => f.properties.valuation_no === asset) : null;
    map = new ml.Map({ container: mapEl, style: OFM_STYLE, ...(f0 ? { center: f0.geometry.coordinates, zoom: 15.2 } : { bounds: HK_BOUNDS }),
      attributionControl: false, canvasContextAttributes: { preserveDrawingBuffer: true }, maxPitch: 70 });
    // compact attribution, kept clear of the panels by CSS (left of the drawer on desktop, top-left above the sheets on phones)
    attribution(ml, map, "bottom-right");
    map.addControl(new ml.NavigationControl({ visualizePitch: true }), "top-right");
    window.__rt = { ...(window.__rt ?? {}), exploreMap: map };
    map.on("load", () => {
      addLayers(map, scenario);
      if (f0) map.jumpTo({ center: f0.geometry.coordinates, padding: drawerPad() });
      else if (innerWidth > 900) map.fitBounds(HK_BOUNDS, { padding: { left: 400, top: 20, right: 20, bottom: 20 }, duration: 0 });
      ready = true;
    });
    for (const id of ["pts", "fp"]) {
      map.on("click", id, (e) => select(e.features[0].properties.valuation_no));
      map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
    }
    map.on("move", () => mapB?.jumpTo({ center: map.getCenter(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() }));
    return () => { map?.remove(); mapB?.remove(); };
  });

  // effects: map styling, 3D, compare, HLC, URL
  $effect(() => { scenario; hazard; sea; asset; filter; hlcOn; if (ready) { restyle(map, scenario); restyle(mapB, "baseline"); } });
  $effect(() => { if (ready && hazard === "landslide" && hlcOn) ensureHlc(); });
  // sea level context polygons (2.2 MB) load only when the layer is switched on
  $effect(() => {
    if (!ready || sea == null || extents) return;
    getJSON(fetch, "flood_extents.geojson").then((e) => { extents = e; for (const m of [map, mapB]) m?.getSource("ext")?.setData(e); });
  });
  $effect(() => {
    if (!ready) return;
    if (view3d) { map.setTerrain({ source: "dem", exaggeration: 1.3 }); map.easeTo({ pitch: 55, duration: 0 }); }
    else { map.setTerrain(null); map.easeTo({ pitch: 0, duration: 0 }); }
  });
  $effect(() => {
    if (!ready || !compare || hazard !== "coastal" || mapB) return;
    mapB = new ml.Map({ container: mapBEl, style: OFM_STYLE, center: map.getCenter(), zoom: map.getZoom(), interactive: false, attributionControl: false,
      canvasContextAttributes: { preserveDrawingBuffer: true } });
    mapB.on("load", () => addLayers(mapB, "baseline"));
  });
  $effect(() => {
    if (!ready) return;
    setQuery({ scenario, asset, hazard: hazard === "coastal" ? null : hazard, sea, compare: compare ? 1 : null, filter, view: view3d ? "3d" : null });
  });
</script>

<Seo title="Explore" description="Map of Link REIT's Hong Kong properties by coastal flood, rain flood and landslide risk under four climate scenarios." path="/explore/" />

<main id="main" class="explore" class:has-drawer={!!selected}>
  <div class="maps">
    <div class="map" bind:this={mapEl} role="region" aria-label="Map of Link's Hong Kong properties. Use the search box to select a property.">
      {#if !ready}<div class="map-skeleton">Map loading…</div>{/if}
    </div>
    <div class="map map-b" bind:this={mapBEl} aria-hidden="true" hidden={!(compare && hazard === "coastal")} style="clip-path: inset(0 {100 - swipeX}% 0 0)"></div>
    {#if compare && hazard === "coastal"}
      <div class="swipe" style="--x:{swipeX}%">
        <span class="swipe-tag left">{SHORT.baseline}</span><span class="swipe-tag right">{SHORT[scenario]}</span>
        <button class="swipe-handle" role="slider" aria-label="Compare position" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(swipeX)}
          onpointerdown={swipeDown} onkeydown={(e) => { if (e.key === "ArrowLeft") setX(swipeX - 5); if (e.key === "ArrowRight") setX(swipeX + 5); }}><span aria-hidden="true">⟷</span></button>
      </div>
    {/if}
  </div>

  <Sheet class="panel" bind:snap={panelSnap} label="map controls" aria-labelledby="panel-h">
    <div class="panel-head">
      <h1 id="panel-h">Explore {data.portfolio.n_assets_total} properties</h1>
      <div class="search" role="search">
        <label class="sr-only" for="q">Find a property</label>
        <input id="q" type="search" placeholder="Find a property or district" autocomplete="off" role="combobox" aria-autocomplete="list"
          aria-expanded={hits.length > 0} aria-controls="q-list" aria-activedescendant={activeOpt >= 0 ? `opt-${activeOpt}` : undefined} bind:value={q} onkeydown={searchKey} />
        {#if hits.length}
          <ul id="q-list" class="q-list" role="listbox">
            {#each hits as h, i}
              <li role="option" id="opt-{i}" aria-selected={i === activeOpt} onclick={() => pick(h.valuation_no)} onkeydown={() => {}}>{cleanName(h.name)}<small>{h.district}</small></li>
            {/each}
          </ul>
        {/if}
      </div>
    </div>
    <div class="tabs" role="tablist" aria-label="Hazard">
      {#each HAZARDS as [k, label], i}
        <button role="tab" id="t-{k}" aria-controls="p-{k}" aria-selected={hazard === k} tabindex={hazard === k ? 0 : -1} onclick={() => (hazard = k)} onkeydown={(e) => tabKey(e, i)}>{label}</button>
      {/each}
    </div>
    <div class="panel-body">
      {#if hazard !== "heat"}
        <div role="tabpanel" id="p-{hazard}" aria-labelledby="t-{hazard}">
          {#if hazard === "coastal"}
            <fieldset class="seg"><legend>Climate scenario</legend>
              {#each SCENARIOS as s}<label><input type="radio" name="scenario" value={s} bind:group={scenario} /><span>{SHORT[s]}</span></label>{/each}
            </fieldset>
            <p class="hint">{SCENARIO_NOTE[scenario]}</p>
            <div class="legend"><p class="hint" style="margin:0">Colour: the most frequent sea level that reaches the site.</p>
              {#each RP_CLASSES as c}<div><i style="background:{c.color}"></i>{c.label}</div>{/each}
              <div><i style="background:{COLORS.none};border-color:{COLORS.none}"></i>Not reached within 200 years</div>
              <div><i class="hollow"></i>Approximate location (30 m circle)</div></div>
          {:else}
            <p>{hazard === "rain" ? "Our rain-flood indicator: closeness to known flood-prone spots, local low ground and basements." : "Our landslide indicator from terrain slope and nearby historical landslide catchments; not GEO data."} A screening indicator, not a probability.</p>
            <div class="legend">{#each ["low", "medium", "high"] as c}<div><i style="background:{CLASS3[c]}"></i>{c[0].toUpperCase() + c.slice(1)}</div>{/each}</div>
            {#if hazard === "landslide"}
              <label class="switch" style="margin-top:12px"><input type="checkbox" bind:checked={hlcOn} /> <span>Historical landslide catchments</span></label>
              <p class="attr">Historical Landslide Catchments: Geotechnical Engineering Office, Civil Engineering and Development Department (GEO, CEDD)</p>
            {/if}
          {/if}
        </div>
      {:else}
        <div role="tabpanel" id="p-heat" aria-labelledby="t-heat">
          <p>Heat is projected for Hong Kong as a whole, so it cannot rank properties.</p>
          <div class="heat-fig"><div><b>{H.very_hot_days_baseline} → {H.very_hot_days_ssp245_2050}</b><span>very hot days a year (max ≥ 33 °C), 1995–2014 → 2050, SSP2-4.5</span></div>
            <div><b>{H.hot_nights_baseline} → {H.hot_nights_ssp245_2050}</b><span>hot nights a year (min ≥ 28 °C)</span></div></div>
          <p>If cooling demand rose 10–20%, Link's Hong Kong air-conditioning bill would rise by about <strong>{hkdRange(H.whatif_extra_cost_hkd)}</strong> a year: {H.whatif_label}.</p>
          <p class="attr">Hong Kong Observatory climate projections (2041–2060 mean).</p>
        </div>
      {/if}

      <div class="tool"><h2>Filter</h2>
        <div class="chips" role="group" aria-label="Show only">
          {#each FILTERS as [k, label]}<button aria-pressed={filter === k} onclick={() => (filter = filter === k ? null : k)}>{label}</button>{/each}
        </div>
        <p class="hint">Tier 1: in the top {M.top_n} in at least {M.tier1_min_survival} of {M.weight_variants} weightings of coastal, rain and landslide risk.</p>
      </div>
      {#if hazard === "coastal"}
        <div class="tool">
          <label class="switch"><input type="checkbox" checked={sea != null} onchange={(e) => (sea = e.currentTarget.checked ? 4 : null)} /> <span>Sea level context</span></label>
          {#if sea != null}
            <div class="sea">
              <label for="sea">Land below <strong class="num">{sea}</strong> m above datum (5 m terrain model; coarse, 1 m steps; illustrative)</label>
              <input type="range" id="sea" min="3" max="7" step="1" bind:value={sea} />
              <div class="ticks num" aria-hidden="true">{#each [3, 4, 5, 6, 7] as t}<span>{t}</span>{/each}</div>
              <p class="hint">Land connected to the sea at or below this height, with no defences. Property markers do not change: their results use 2020 LiDAR.</p>
            </div>
          {/if}
        </div>
        <div class="tool"><label class="switch"><input type="checkbox" bind:checked={compare} /> <span>Compare with 1995–2014 (swipe)</span></label></div>
      {/if}
      <div class="tool"><label class="switch"><input type="checkbox" bind:checked={view3d} /> <span>3D terrain and buildings</span></label></div>
    </div>
    <p class="attr panel-foot">{data.meta.terrain.attribution}. Footprints: Lands Department iB1000 via CSDI Portal.</p>
  </Sheet>

  {#if selected}
    <Sheet class="drawer" bind:snap={drawerSnap} label="property details" aria-labelledby="d-name">
      <AssetPanel p={selected.properties} coords={selected.geometry.coordinates} {scenario} adapt={adaptBy.get(asset)} margin={marginBy.get(asset)}
        {footprints} {ml} discount={A.discount_rate} horizon={A.horizon_years} onclose={() => (asset = null)} />
    </Sheet>
  {/if}
</main>
