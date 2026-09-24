# Phase 2 Web-Reference Source Registry

Verified: 2026-09-24

Purpose: identify authoritative public pages that expose useful package/product imagery for the `web_reference` dataset class.

The image files themselves remain local and ignored by Git. Before using an image:

1. confirm it is an actual package/product image rather than a campaign-only graphic;
2. save the original bytes without editing;
3. record the exact source page in `source_page_url`;
4. keep the generated SHA-256 in the evaluation report;
5. classify it as `web_reference`, never `real_package`.

## Candidate official sources

| Brand / product | Official source page | Why useful |
| --- | --- | --- |
| Parle-G | https://www.parleproducts.com/brands/parle-g | Official Parle-G family/package imagery |
| Parle-G Gluco | https://www.parleproducts.com/brands/parle-g-gluco | Multiple official Gluco product images |
| Britannia Good Day | https://www.britannia.co.in/product/good-day | Multiple Good Day variants and pack imagery |
| Britannia Bourbon | https://www.britannia.co.in/product/bourbon | Official Bourbon pack imagery |
| MAGGI 2-Minute Masala Noodles | https://www.nestle.in/brands/maggi2-minutenoodles | Official Nestlé India product imagery |
| MAGGI Korean Noodles | https://www.nestle.in/brands/foods/maggi-korean-noodles | Official package/product imagery for a different pack design |
| MAGGI Hungrooo | https://www.nestle.in/brands/maggi-hungrooo | Official larger-pack variant imagery |
| Haldiram's Aloo Bhujia | https://haldirams.com/products/aloo-bhujia | Official retail product page |
| Haldiram's Bhujia Sev | https://www.haldirams.com/product/bestsellers/bhujia-sev | Official retail product page |
| Lay's India refreshed packaging | https://www.pepsicoindia.co.in/our-stories/press-release/lay-s-brings-its-biggest-global-brand-refresh-to-india-highlighting-quality-ingredients/ | Official PepsiCo India page discussing and showing refreshed packs |

## Selection guidance

Do not take only perfect front-facing hero images.

Prefer a diverse web-reference set where available:

- different brands and package shapes;
- different background colors and print density;
- front/oblique/package-family views;
- packaging with small text where the source resolution supports it;
- both rigid-looking and flexible-pack designs.

Avoid counting multiple resized copies of the same source asset as independent cases.

## Evidence boundary

These sources are appropriate for:

- validating that the pipeline can ingest real commercial package imagery;
- observing quality and geometry heuristic behavior on diverse packaging;
- later OCR/declaration experimentation when the image resolution is sufficient.

They do not reproduce field conditions such as:

- handheld blur;
- uncontrolled glare;
- low light;
- camera perspective from an inspector;
- crumpled or partially occluded packages.

Therefore they remain `web_reference` evidence and do not satisfy the real-package field-capture gate.
