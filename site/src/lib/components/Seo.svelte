<script>
  import { base } from "$app/paths";
  import { SITE_URL, SITE_NAME } from "$lib/site.js";
  let { title, description, path = "/" } = $props();
  const og = `${SITE_URL || base}/og.png`;
</script>

<svelte:head>
  <title>{title} · {SITE_NAME}</title>
  <meta name="description" content={description} />
  {#if SITE_URL}<link rel="canonical" href="{SITE_URL}{path}" />{/if}
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content={SITE_NAME} />
  <meta property="og:title" content="{title} · {SITE_NAME}" />
  <meta property="og:description" content={description} />
  <meta property="og:image" content={og} />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:alt" content="Rising Tide: small, concentrated, rising. Coastal flood risk in Link REIT's Hong Kong portfolio." />
  <meta name="twitter:card" content="summary_large_image" />
</svelte:head>
