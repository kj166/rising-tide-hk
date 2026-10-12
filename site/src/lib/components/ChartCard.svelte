<script>
  // One takeaway sentence + one Observable Plot chart + Chart/Table tabs + source line + CSV download
  import PlotFigure from "./PlotFigure.svelte";
  let { id, kicker, title, make, label, table, source, wide = false, summary = "", after } = $props();
  let view = $state("chart");
  function download() {
    const csv = [table.cols, ...table.csv].map((r) => r.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(",")).join("\n");
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([csv], { type: "text/csv" })), download: `${id}.csv` });
    a.click();
  }
  function key(e) { if (e.key === "ArrowLeft" || e.key === "ArrowRight") { view = view === "chart" ? "table" : "chart"; document.getElementById(`${id}-t${view === "chart" ? "c" : "t"}`)?.focus(); } }
</script>

<article class="card" class:wide aria-labelledby="{id}-h">
  <p class="card-kicker">{kicker}</p>
  <h2 id="{id}-h">{title}</h2>
  {#if summary}<p class="card-summary num">{summary}</p>{/if}
  <div class="card-bar">
    <div class="vt" role="tablist" aria-label="View">
      <button role="tab" id="{id}-tc" aria-controls="{id}-c" aria-selected={view === "chart"} tabindex={view === "chart" ? 0 : -1} onclick={() => (view = "chart")} onkeydown={key}>Chart</button>
      <button role="tab" id="{id}-tt" aria-controls="{id}-t" aria-selected={view === "table"} tabindex={view === "table" ? 0 : -1} onclick={() => (view = "table")} onkeydown={key}>Table</button>
    </div>
    <button class="dl" onclick={download}>Download CSV</button>
  </div>
  <div id="{id}-c" role="tabpanel" aria-labelledby="{id}-tc" hidden={view !== "chart"}><PlotFigure {make} {label} fallback="Chart loads with JavaScript; the Table tab has the values." /></div>
  <div class="tbl" id="{id}-t" role="tabpanel" aria-labelledby="{id}-tt" hidden={view !== "table"}>
    <table>
      <thead><tr>{#each table.cols as c}<th scope="col">{c}</th>{/each}</tr></thead>
      <tbody>{#each table.rows as r}<tr>{#each r as v}<td>{v}</td>{/each}</tr>{/each}</tbody>
    </table>
  </div>
  {#if after}{@render after()}{/if}
  <p class="source">{source}</p>
</article>
