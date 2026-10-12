<script>
  import { base } from "$app/paths";
  import { page } from "$app/state";
  // dark = over the Story hero: transparent on a gradient scrim, solid off-white once the hero has scrolled away
  let { dark = false } = $props();
  let solid = $state(false);
  $effect(() => {
    if (!dark) return;
    const hero = document.querySelector(".hero");
    const check = () => { solid = !hero || scrollY > hero.offsetHeight - 64; };
    check();
    addEventListener("scroll", check, { passive: true });
    addEventListener("resize", check);
    return () => { removeEventListener("scroll", check); removeEventListener("resize", check); };
  });
  const links = [["/", "Story"], ["/explore/", "Explore"], ["/insights/", "Insights"], ["/method/", "Method"]];
  const current = (href) => page.url.pathname === `${base}${href}`;
  // carry scenario and asset to Explore / Insights at click time (shareable state; read from the live URL)
  function carry(e, href) {
    if (href !== "/explore/") return;
    const cur = new URLSearchParams(location.search), q = new URLSearchParams();
    for (const k of ["scenario", "asset"]) { const v = cur.get(k); if (v) q.set(k, v); }
    if (q.toString()) e.currentTarget.href = `${base}${href}?${q}`;
  }
</script>

<a class="skip" href="#main">Skip to content</a>
<header class="topbar" class:dark class:solid={dark && solid}>
  <a class="wordmark" href="{base}/">
    <svg class="wave" viewBox="0 0 22 14" aria-hidden="true"><path d="M1 9c3-4 6-4 9 0s6 4 9 0" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><path d="M1 4c3-3 6-3 9 0s6 3 9 0" fill="none" stroke="#0E7C86" stroke-width="2.2" stroke-linecap="round"/></svg>
    <b>Rising Tide</b><span class="wm-sub">Link REIT · Hong Kong climate risk</span>
  </a>
  <nav class="nav" aria-label="Pages">
    {#each links as [href, label]}
      <a href="{base}{href}" onclick={(e) => carry(e, href)} aria-current={current(href) ? "page" : undefined}>{label}</a>
    {/each}
  </nav>
</header>
