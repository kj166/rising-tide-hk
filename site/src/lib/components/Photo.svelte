<script>
  import { base } from "$app/paths";
  // Commons photo (data/manual/photo_credits.csv). crop = fill a 3:2 frame (object-fit: cover); only for photos whose
  // adaptation column says "cropped", so the credit line (photos.json) already reads "cropped (adaptation)".
  let { photo, sizes = "(min-width: 900px) 440px, 100vw", eager = false, crop = false } = $props();
  const srcset = $derived(photo.srcset_webp.split(", ").map((s) => `${base}/${s}`).join(", "));
  $effect(() => { if (crop && !photo.adaptation.startsWith("cropped")) throw new Error(`${photo.src}: crop not recorded as an adaptation`); });
</script>

<figure class="photo" class:crop>
  <picture>
    <source type="image/webp" {srcset} {sizes} />
    <img src="{base}/{photo.src}" width={photo.width} height={photo.height} alt={photo.alt} loading={eager ? "eager" : "lazy"} decoding="async" />
  </picture>
  <figcaption>{photo.caption} <span class="credit"><a href={photo.page}>{photo.credit}</a></span></figcaption>
</figure>
