# Data sources and regeneration instructions

How the Excipient Sourcing Navigator's data is built, and what to update when the underlying excipient or supplier data changes.

## Source files

All sources live in `ea-work/data-for-reoccurring-tasks/`.

| File | Drives | What it provides |
|------|--------|------------------|
| `excipients-landscape-structure-v2.md` | Stages 2-4 | Route (`#`) > category (`##`) > excipient (`- `). Nothing else; no suppliers on these lines |
| `excipient-products-tree.md` | Stages 5-6 | Excipient (`##`) > supplier (`###`) > product bullets, with the e-shop links already matched in |
| `supplier-page-urls.md` | Stage 5 | Each supplier's PharmaExcipients.com page link |

The two files join on the **exact excipient name**: every `- Excipient` line in the structure file must have a matching `## Excipient` heading in the product tree.

## Stages

1. Landing
2. Route of administration (Oral, Injectable, Inhalation / Pulmonary, Nasal, Topical, Ocular, Rectal & Vaginal)
3. Functional category
4. Excipient
5. Supplier (with a link to the supplier's PharmaExcipients.com page)
6. Products for that excipient and supplier, linked to the e-shop

## How the files combine

- `excipients.json` (stages 2-5) takes the taxonomy from the structure file. Each excipient's supplier list is whoever has a `###` section under that excipient in the product tree, with the portal link looked up in `supplier-page-urls.md`.
- `products.json` (stage 6) is the product tree, keyed excipient > supplier. Because products are filed under a specific excipient at source, stage 6 is a direct lookup and the browser does no matching.

## Regenerating the data

After updating any source file, run from the project folder:

```bash
python3 build-data.py
```

This rewrites `excipients.json` and `products.json` and prints a summary: route, category, excipient, supplier, and product counts, the e-shop link rate, the primary-versus-minor split, the suppliers with no portal page, and the excipients with no supplier. Any product bullet the script cannot parse, or any tree excipient with no place in the taxonomy, is reported as a warning and the script exits non-zero so it gets fixed before the data ships.

## Format conventions to keep so future updates stay parseable

- **Product bullet format** in `excipient-products-tree.md`:
  ```
  - Product name — chemical/generic name — [n] involvement tag — function → [Shop label](url), [Shop label](url)
  ```
  Four fields separated by ` — ` (space, em dash, space), then the links after ` → `. The links are optional. All four fields are required; the build rejects any bullet that does not match.
- **Involvement tags** drive the stage 6 ordering. Tags 1, 2, and 3 mean the excipient is the substance or a primary component, and those products are listed first. Tags 4, 5, and 6 mean it is a minor or derived component, listed after.
- **No supplier for an excipient:** give the excipient a `##` heading with no `###` sections under it, or leave it out of the tree entirely. Either way the tool shows the "currently unavailable" note.
- **No portal page for a supplier:** put `--` in the URL column of `supplier-page-urls.md`, or leave the supplier out of that file. The supplier still appears in the tool, just without the Supplier Page button.
- **Supplier naming:** use one spelling per company. Two aliases are currently corrected in `build-data.py` (`ShinEtsu` to `Shin-Etsu`, `Sudzucker` to `Südzucker AG`). Add to `SUPPLIER_ALIASES` there if another variant appears, or fix it at source.
- **Excluded sections:** `Unknown Supplier` and the tree's `Unclassified` excipient are dropped by the build. Both lists are at the top of `build-data.py`.
- **New excipient names** must match between the two files exactly. If they drift, the excipient shows as unavailable and the build warns about an orphaned tree section.

## No longer used

The v1 pipeline read `excipients-landscape-structure-suppliers.md`, `excipient-suppliers-list.md`, `excipient-products-by-supplier.md`, and `pe-shop-products-complete.csv`, and matched shop URLs by normalized product name. The product tree now carries the chemical name, function, and e-shop links inline, so none of those files are part of the build.

## Last updated

2026-07-27
