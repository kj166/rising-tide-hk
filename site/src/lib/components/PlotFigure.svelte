<script>
  // Client-side Observable Plot render; `make(width)` returns an SVG/HTML element. Text fallback for no-JS.
  import { onMount } from "svelte";
  let { make, label, fallback = "" } = $props();
  let el;
  onMount(() => {
    const draw = () => {
      const node = make(Math.max(280, el.clientWidth));
      // Plot labels its <g> groups; aria-label is not allowed on role-less <g> (the SVG keeps its label + description)
      node.querySelectorAll?.("g[aria-label]").forEach((g) => g.removeAttribute("aria-label"));
      el.replaceChildren(node);
    };
    draw();
    const ro = new ResizeObserver(() => draw());
    ro.observe(el);
    return () => ro.disconnect();
  });
</script>

<figure class="chart" bind:this={el} aria-label={label} style="margin:0; min-height: 60px"><p class="note">{fallback}</p></figure>
