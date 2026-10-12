<script>
  import "../app.css";
  import { page } from "$app/state";
  import TopBar from "$lib/components/TopBar.svelte";
  import Footer from "$lib/components/Footer.svelte";
  let { data, children } = $props();
  const dark = $derived(page.route.id === "/");
</script>

<TopBar {dark} />
{@render children()}
<Footer meta={data.meta} photos={data.photos} />
