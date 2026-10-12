<script>
  import { SHOW_LANDSD_AERIAL } from "$lib/config.js";
  let { meta, photos } = $props();
  const NON_ENDORSEMENT = "Independent student project; not endorsed by GEO, CEDD, LandsD, HKO or Link REIT.";
</script>

<footer class="site-foot">
  <div class="foot-in">
    <p><b>Rising Tide</b> · Lee Pak Kiu Jeff · October 2026 · Built with Claude Code</p>
    <p class="non-endorse">{NON_ENDORSEMENT}</p>
    <div class="foot-grid">
      <div>
        <p class="attr" style="margin:0"><b style="font:600 .8rem var(--font-body)">Data attributions</b></p>
        <ul>
          <li>Historical Landslide Catchments: Geotechnical Engineering Office, Civil Engineering and Development Department (GEO, CEDD). Our landslide indicator is our own derived metric, not GEO data.</li>
          <li>Building footprints derived from iB1000 Digital Topographic Map, Lands Department, HKSAR Government, via the CSDI Portal. Intellectual property rights in the data belong to the HKSAR Government.</li>
          <li>{meta.terrain.attribution}. Ground levels: CEDD 2020 LiDAR Digital Terrain Model via the CSDI Portal.</li>
          <li>Climate projection figures: Hong Kong Observatory. The Government of the HKSAR owns the intellectual property rights; figures are cited, not reproduced as tables.</li>
          <li>Basemap: OpenFreeMap © OpenMapTiles, data from OpenStreetMap contributors.</li>
          <li>Data are provided "as is" by their owners; no warranty is given by them for this use.</li>
        </ul>
      </div>
      <div>
        <p class="attr" style="margin:0"><b style="font:600 .8rem var(--font-body)">Photo credits (Wikimedia Commons)</b></p>
        <ul>
          {#each Object.values(photos) as p}
            <li><a href={p.page}>{p.credit}</a>{p.adaptation.startsWith("cropped") ? `; ${p.adaptation.split(";")[0]}` : ""}</li>
          {/each}
        </ul>
      </div>
    </div>
  </div>
</footer>
