# Data sources and regeneration instructions

How the Excipient Sourcing Navigator's data is built, and what to update when the underlying excipient or supplier data changes.

## Source files

All sources live in `ea-work/data-for-reoccurring-tasks/`.

| File | Drives | What it provides |
|------|--------|------------------|
| `excipients-landscape-structure-suppliers.md` | Stages 2-5 | The full tree: route (`#`) > category (`##`) > excipient (`-`), with suppliers after an em dash per excipient line |
| `excipient-suppliers-list.md` | Stage 5 | Canonical roster of the 39 supplier names; used to normalize naming so it matches across files |
| `supplier-page-urls.md` | Stage 5 | Each supplier's PharmaExcipients.com page link |
| `excipient-products-by-supplier.md` | Stage 6 | Products per supplier (product name, chemical/generic name, function) |
| `pe-shop-products-complete.csv` | Stage 6 | Shop export (`name`, `url` columns); product links come from matching product names here |

## Stages

1. Landing
2. Route of administration (Oral, Injectable, Inhalation / Pulmonary, Nasal, Topical, Ocular, Rectal & Vaginal)
3. Functional category
4. Excipient
5. Supplier (with a link to the supplier's PharmaExcipients.com page)
6. Products for that excipient and supplier (linked to the shop where a match exists)

## How the files combine

- `excipients.json` (stages 2-5) is built from `excipients-landscape-structure-suppliers.md`, `excipient-suppliers-list.md`, and `supplier-page-urls.md`.
- `products.json` (stage 6) is built from `excipient-products-by-supplier.md` and `pe-shop-products-complete.csv`.

## Regenerating the data

After updating any source file, run from the project folder:

```bash
python3 build-data.py
```

This rewrites `excipients.json` and `products.json` and prints a summary (route, category, excipient, and product counts, the list of currently unavailable excipients, the shop-URL match rate, and any unresolved supplier names). If a supplier name cannot be resolved to the canonical roster, the script exits with an error so the mismatch gets fixed before the data ships.

## Format conventions to keep so future updates stay parseable

- **No supplier:** write the excipient as `Excipient Name — (none in supplier list)`. That triggers the "currently unavailable" note instead of supplier buttons.
- **No portal page for a supplier:** put `--` in the URL column of `supplier-page-urls.md`. That supplier then shows no "Supplier Page" button.
- **Supplier naming:** use the exact name from `excipient-suppliers-list.md`. A unique shorthand still resolves (for example `MEGGLE` maps to `MEGGLE Excipients & Technology`), but exact names are safest.
- **Product links:** matched by exact (normalized) product name against the shop CSV. Products with no match still display, just without a clickable link. The match rate is roughly half, because the products file lists specific grades from broad web research while the shop lists generic names; exact matching is deliberate to avoid mis-linking grades.

## Last updated

2026-06-27
