<script>
  import { base } from "$app/paths";
  import Seo from "$lib/components/Seo.svelte";
  import Photo from "$lib/components/Photo.svelte";
  import { SOURCES, IMAGERY_SOURCE } from "$lib/sources.js";
  import { SHOW_LANDSD_AERIAL } from "$lib/config.js";
  import { cleanName } from "$lib/format.js";

  let { data } = $props();
  const M = data.meta.method, P = data.portfolio, A = data.adaptation, SC = data.scorecard;
  const W = M.ranking_weights;
  const pc = (x) => `${Math.round(x * 100)}%`;
  const sources = SHOW_LANDSD_AERIAL ? [...SOURCES, IMAGERY_SOURCE] : SOURCES;
  const files = ["portfolio.json", "assets.geojson", "footprints.geojson", "margins.json", "adaptation.json", "scorecard.json", "heat.json", "flood_extents.geojson", "hlc.geojson", "meta.json"];
</script>

<Seo title="Method & About" description="How the Rising Tide study estimates coastal flood, rain flood, landslide and heat risk for Link REIT's Hong Kong properties, and its limitations." path="/method/" />

<main id="main" class="method">
  <header>
    <p class="eyebrow">Method &amp; About</p>
    <h1>How the numbers are made</h1>
    <p class="lede">Each section says what we did in plain language. Open "Technical detail" for the specifics.</p>
  </header>

  <section class="method-sec" aria-labelledby="m1">
    <h2 id="m1">Where the properties are</h2>
    <p>We placed all {P.n_assets_total} Hong Kong properties on the map and matched {P.n_footprints} to building outlines from the Lands Department's iB1000 map. The other {M.n_location_approximate} use a 30 m circle around an approximate location.</p>
    <p id="assessed">{P.n_assets_total} properties are mapped; {P.n_assets} are assessed for flood loss. {P.under_development_names.map(cleanName).join(", ")} was still under development on 31 March 2026, with no built floor area or rental income in Link's valuation report, so no replacement cost, and no loss, can be estimated for it. It stays on the map with its rain and landslide indicators.</p>
    <details><summary>Technical detail</summary><div><p>Locations come from the HK Address Lookup Service with manual checks. Footprints are iB1000 building blocks named as the property plus touching blocks, reviewed by hand. Ground levels come from the CEDD 2020 LiDAR terrain model (0.5 m cells).</p></div></details>
  </section>

  <section class="method-sec" aria-labelledby="m2">
    <h2 id="m2">Coastal flooding</h2>
    <p>For each property we ask how high the sea must rise before water reaches it, then how often that happens: once in 2, 5, 10 … or 200 years.</p>
    <details><summary>Technical detail</summary><div>
      <p>Still-water level = extreme sea level (Port Works Design Manual, CEDD, Corrigendum 2022) + HKO sea-level rise + the projected storm-surge increase. Water reaches a property when the level passes the lowest ground on its route from the sea (LiDAR) and its entrance.</p>
      <p>Ground levels carry a ±{M.onset_accuracy_m} m range, shown on every result. "1995–2014 climate" is the projections' base period, not today.</p>
    </div></details>
  </section>

  <section class="method-sec" aria-labelledby="m3">
    <h2 id="m3">From water to money</h2>
    <p>Water inside a building damages it and closes it while it is repaired. We price both, then average over all storm sizes to get an expected loss per year.</p>
    <details><summary>Technical detail</summary><div>
      <p>Damage: JRC Asia commercial depth-damage curve applied to the ground-floor share of replacement cost. Closure: FEMA Hazus 7.0 maximum restoration times (US defaults, an upper bound); the lower figure uses {pc(M.bi_days_factor_low)} of those days.</p>
      <p>Expected annual loss integrates events from 1-in-{M.eal_return_periods[0]} to 1-in-{M.eal_return_periods[1]} years; the upper figure adds rarer events held at the 1-in-{M.eal_return_periods[1]} loss.</p>
    </div></details>
  </section>

  <section class="method-sec" aria-labelledby="m4">
    <h2 id="m4">Rain, landslides and heat</h2>
    <p>Rain flooding and landslides are screening indicators, not probabilities. Heat is projected for Hong Kong as a whole, so we report it for the portfolio only.</p>
    <details><summary>Technical detail</summary><div>
      <p>Rain: closeness to the Drainage Services Department's flood-prone locations, local low spots and basements, scaled by HKO's projected change in maximum daily rainfall. Landslide: terrain slope and nearby Historical Landslide Catchments (GEO, CEDD); our metric, not GEO data.</p>
      <p>Heat: HKO projections of very hot days and hot nights, plus an illustrative cooling-cost what-if.</p>
    </div></details>
  </section>

  <section class="method-sec" aria-labelledby="m5">
    <h2 id="m5">Tiers, hotspots and barriers</h2>
    <p>We combine coastal, rain and landslide risk into tiers, list the top properties on each hazard, and estimate what a flood barrier would be worth.</p>
    <details><summary>Technical detail</summary><div>
      <p>Weights: coastal {pc(W.coastal_flood)}, rain {pc(W.rain_flood)}, landslide {pc(W.landslide)}, tested over {M.weight_variants} combinations. Tier 1 = in the top {M.top_n} in at least {M.tier1_min_survival} of them. Hotspots: top {M.hotspot_top_n} per hazard; the first on any hazard is an asset to watch.</p>
      <p>Barriers of {M.barrier_heights_m.join(" m and ")} m: break-even budget = present value of avoided loss over {M.horizon_years} years at {pc(M.discount_rates[0])} (also {M.discount_rates.slice(1).map(pc).join(" and ")}).</p>
    </div></details>
  </section>

  <section class="method-sec" aria-labelledby="m6">
    <h2 id="m6">Rounding</h2>
    <p>Money is rounded to two significant figures and shown as a range. Shares are rounded to two significant figures too, without decimals (for example {Math.round(P.scenarios.ssp245_2050.top3_share_pct[0])}–{Math.round(P.scenarios.ssp245_2050.top3_share_pct[1])}%).</p>
  </section>

  <section class="method-sec" aria-labelledby="m7">
    <h2 id="m7">How we read Link's disclosure</h2>
    <p>Link says its sustainability report follows the HKEX Appendix C2 climate requirements. We score {SC.items.length} items against that self-declared alignment, with TCFD and IFRS S2 as reference: {SC.total} of {SC.max}.</p>
    <details><summary>Technical detail</summary><div><p>Whether Appendix C2 formally applies to a listed REIT is not shown by the rules we read, and we do not assume it either way. A low score marks a gap in disclosure, never a breach of any rule.</p></div></details>
  </section>

  <section class="method-sec" aria-labelledby="lim">
    <h2 id="lim">Limitations</h2>
    <div class="limits-grid">
      <Photo photo={data.photos.wm5_central_harbourfront_mangkhut} sizes="(min-width: 900px) 560px, 100vw" />
      <ul class="limits">
        <li><b>Still water only, no waves.</b> Seafront risk is understated.</li>
        <li><b>Thresholds.</b> Whether water enters can turn on a few centimetres; every flood result carries a ±{M.onset_accuracy_m} m range.</li>
        <li><b>Closure costs are an upper bound</b> (US default restoration times).</li>
        <li><b>Rain and landslide are screening indicators,</b> not probabilities.</li>
        <li><b>Heat is territory-wide,</b> so it cannot rank properties.</li>
        <li><b>{M.n_location_approximate} locations are approximate</b> where no building outline could be matched.</li>
        <li><b>Sea level context is coarse:</b> the 5 m terrain model is in whole metres and shows no sea walls or drains.</li>
      </ul>
    </div>
  </section>

  <section class="method-sec" aria-labelledby="src">
    <h2 id="src">Sources</h2>
    <ul class="sources">{#each sources as [t, u]}<li><a href={u}>{t}</a></li>{/each}</ul>
  </section>

  <section class="method-sec" aria-labelledby="dl">
    <h2 id="dl">Download the data</h2>
    <p>Our derived results, exactly as this site uses them (attributions in the footer apply).</p>
    <ul class="sources">{#each files as f}<li><a href="{base}/data/{f}" download>{f}</a></li>{/each}</ul>
  </section>

  <section class="method-sec" aria-labelledby="how">
    <h2 id="how">How I built this</h2>
    <p><b>Why I built it.</b> I wanted to see whether an interactive website could help a company understand its physical climate risk, and the case for adapting to it, in terms that an ESG team, a finance team and a facilities team can each use. Link REIT's Hong Kong portfolio offered a real asset-by-asset test, because Link publishes enough property-level information for its exposure to be modelled from public documents.</p>
    <p><b>What was hard.</b> Most of the work was sorting very different kinds of data (sea-level tables, terrain models, damage curves, valuation reports and disclosures) and deciding which parts were useful. The second challenge was building a transparent model that turns water levels into expected losses, carrying the uncertainty through instead of hiding it.</p>
    <p><b>What I checked myself.</b> I compared every number transcribed from a source document with the original, and checked property locations against building outlines and satellite imagery. I also asked whether the model behaves sensibly: I replayed Typhoon Mangkhut, compared the scale of the losses with Link's reported insurance claims, checked that the highest rain-risk property is one reported flooded in September 2023, and tested the ranking under 27 different weightings.</p>
    <p><b>How I used AI.</b> I used Claude for advice on method and Claude Code to write the code. I verified the inputs against their sources and approved what was published.</p>
  </section>

  <section class="method-sec" aria-labelledby="about">
    <h2 id="about">About</h2>
    <p><b>Lee Pak Kiu Jeff</b>. Independent student project.</p>
    <p>Source code and published data: <a href="https://github.com/kj166/rising-tide-hk">github.com/kj166/rising-tide-hk</a></p>
  </section>
</main>
