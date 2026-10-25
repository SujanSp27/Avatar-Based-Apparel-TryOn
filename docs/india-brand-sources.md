# India clothing size chart verification — 20 October 2026

Men's and women's coverage is tracked independently. Only a verified body-size
table is eligible for body-to-size scoring. Sources describe specific products;
the database does not claim that every product in a brand uses the same chart.

| Brand | Men's India guide | Women's India guide | Recommendation status |
|---|---|---|---|
| Nike | [Dri-FIT T-shirt HV4188-013](https://www.nike.in/nike-men-s-dri-fit-t-shirt/p/27753405) | [Chill Knit IM6415-133](https://www.nike.in/nike-sportswear-chill-knit-women-s-slim-mod-cropped-t-shirt/p/27753683) | Enabled for these two T-shirts |
| Puma | [Premium Essentials 634184](https://in.puma.com/in/en/pd/premium-essentials-mens-graphic-t-shirt/634184) | [Essentials Elevated Polo 691419](https://in.puma.com/in/en/pd/essentials-elevated-womens-logo-polo-t-shirt/691419?swatch=65) | Enabled for these two T-shirts |
| U.S. Polo Assn. | [India men's polo](https://uspoloassn.in/collections/aw26-americana-shop-all/products/menswear-solid-muscle-fit-polo-shirt-d7ypv1zgm5z) | [India women's polo](https://uspoloassn.in/products/womenswear-boxy-fit-solid-polo-shirt-6szenlweh8y) | Not enabled: published garment dimensions are not body ranges |
| Adidas | [India men's guide](https://www.adidas.co.in/help/size_charts/men-shirts-tops) | [India women's guide](https://www.adidas.co.in/help/size_charts/women-shirts-tops) | Not enabled: access denied; no verified India table recovered |
| Allen Solly | [India men's shirt](https://allensolly.abfrl.in/p/men-navy-slim-fit-solid-full-sleeves-casual-shirts-892194.html) | [India women's sweatshirt](https://allensolly.abfrl.in/p/allen-solly-blue-sweatshirt-637800.html) | Not enabled: interactive size guide inaccessible; model-worn sizes do not establish ranges |

The Nike India site identifies its tables as body measurements for the product.
The Puma India dialogs contain both body and product tables: only the body table
was transcribed. Bust/chest maps to `chest_circumference`; low hip maps to
`hip_circumference`. Numeric bounds were converted from inches by exactly 2.54.
Source size-label spelling is retained, including Puma men's `XXL` versus women's
`2XL`. Source gaps and overlaps were not silently changed.

Files:

- `india-body-charts-v1.json`: four usable immutable chart versions, 25 size rows.
- `india-chart-sources-v1.json`: transcribed source bounds in inches, URLs, retrieval
  dates and SHA-256 of the locally inspected visible dialog text.
- `india-brand-catalog-v1.json`: all five brands and both genders, including
  explicit unavailable/unverified states.

The cached public page text/screenshots under `.runtime/brand-guides/` supported
the inspection; they are not redistributed. Real product photography was not
uploaded anywhere during this research. Other-market Adidas tables, arbitrary
ease allowances and invented shoulder/thigh measurements were not substituted.

Missing guides can be added through the versioned chart API once verified. This
does not block Nike/Puma sizing, the demonstration six-metric engine, or photo
measurement extraction.
