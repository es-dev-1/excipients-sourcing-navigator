#!/usr/bin/env python3
"""
Regenerate excipients.json (stages 2-5) and products.json (stage 6) for the
Excipient Sourcing Navigator from the source files in
ea-work/data-for-reoccurring-tasks/.

Sources:
  - excipients-landscape-structure-suppliers.md  -> route > category > excipient > suppliers
  - excipient-suppliers-list.md                  -> canonical 39 supplier names
  - supplier-page-urls.md                        -> supplier -> supplier page URL
  - excipient-products-by-supplier.md            -> supplier -> products
  - pe-shop-products-complete.csv                -> product name -> shop URL

Run from the project folder: python3 build-data.py
"""
import csv
import html
import json
import os
import re
import sys
from pathlib import Path

# Source files live in ea-work/data-for-reoccurring-tasks, two levels up from this
# project folder. Resolved relative to this script so it works on any machine.
# Override with the PE_DATA_DIR environment variable if your layout differs.
DATA = Path(os.environ.get(
    "PE_DATA_DIR",
    Path(__file__).resolve().parents[2] / "data-for-reoccurring-tasks",
))
OUT = Path(__file__).parent

STRUCT_MD = DATA / "excipients-landscape-structure-suppliers.md"
SUPPLIERS_MD = DATA / "excipient-suppliers-list.md"
URLS_MD = DATA / "supplier-page-urls.md"
PRODUCTS_MD = DATA / "excipient-products-by-supplier.md"
SHOP_CSV = DATA / "pe-shop-products-complete.csv"

NONE_MARKER = "(none in supplier list)"


def norm_supplier(name):
    """Normalize a supplier name for matching across files."""
    n = name.lower()
    n = re.sub(r"\([^)]*\)", "", n)        # drop parentheticals e.g. (LLS Health)
    n = re.sub(r"[^a-z0-9]+", " ", n)       # punctuation -> space
    return re.sub(r"\s+", " ", n).strip()


def norm_product(name):
    """Normalize a product name for matching md <-> shop CSV."""
    n = html.unescape(name)
    n = n.lower()
    n = n.replace("™", "").replace("®", "").replace("℠", "")  # tm, (r), sm
    n = re.sub(r"[‐-―−]", "-", n)   # all dash variants -> hyphen
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


# ---- 1. canonical supplier names ----
canon = []
for line in SUPPLIERS_MD.read_text().splitlines():
    m = re.match(r"^\|\s*\d+\s*\|\s*(.+?)\s*\|", line)
    if m:
        canon.append(m.group(1).strip())
canon_lookup = {norm_supplier(c): c for c in canon}
assert len(canon) == len(canon_lookup), "duplicate normalized canonical names"


def to_canonical(name, source, errors):
    key = norm_supplier(name)
    if key in canon_lookup:
        return canon_lookup[key]
    # fallback: unique token-boundary prefix match (handles shorthand e.g. "MEGGLE")
    cands = [c for k, c in canon_lookup.items() if k.startswith(key + " ")]
    if len(cands) == 1:
        return cands[0]
    errors.append(f"  UNKNOWN supplier '{name}' (in {source})")
    return name  # keep raw so it is visible, but flagged


errors = []

# ---- 2. supplier page URLs ----
supplier_url = {}
for line in URLS_MD.read_text().splitlines():
    m = re.match(r"^\|\s*(.+?)\s*\|\s*(\S.*?)\s*\|", line)
    if not m:
        continue
    company, url = m.group(1).strip(), m.group(2).strip()
    if company.lower() == "company" or set(company) <= set("-"):
        continue
    if url == "--" or not url.startswith("http"):
        url = None
    key = norm_supplier(company)
    if key in canon_lookup:
        supplier_url[canon_lookup[key]] = url

# ---- 3. structure: routes > categories > excipients > suppliers ----
routes = []
route = cat = None
unavailable = []
for raw in STRUCT_MD.read_text().splitlines():
    line = raw.rstrip()
    if line.startswith("# ") and not line.startswith("## "):
        route = {"name": line[2:].strip(), "children": []}
        routes.append(route)
        cat = None
    elif line.startswith("## "):
        cat = {"name": line[3:].strip(), "children": []}
        route["children"].append(cat)
    elif line.startswith("- "):
        body = line[2:].strip()
        parts = body.split("—", 1)          # split on first em-dash
        exc_name = parts[0].strip()
        sup_str = parts[1].strip() if len(parts) > 1 else ""
        suppliers = []
        if sup_str and sup_str.lower() != NONE_MARKER:
            for s in sup_str.split(","):
                s = s.strip()
                if not s:
                    continue
                cname = to_canonical(s, f"structure '{exc_name}'", errors)
                suppliers.append({"name": cname, "link": supplier_url.get(cname)})
        if not suppliers:
            unavailable.append(f"{route['name']} > {cat['name']} > {exc_name}")
        cat["children"].append({"name": exc_name, "suppliers": suppliers})

# ---- 4. products by supplier ----
products = {}
cur = None
for raw in PRODUCTS_MD.read_text().splitlines():
    line = raw.rstrip()
    mh = re.match(r"^##\s+(?:\d+\.\s*)?(.+)$", line)
    if mh:
        title = mh.group(1).strip()
        if re.match(r"^\d", line[3:].strip()):  # numbered -> a supplier section
            cur = to_canonical(title, "products md header", errors)
            products.setdefault(cur, [])
        else:
            cur = None  # e.g. "## Progress"
        continue
    if cur and line.startswith("|"):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 3:
            continue
        if set(cells[0]) <= set("-: "):            # separator row
            continue
        if cells[0].lower() in ("product name", "product"):  # header row
            continue
        products[cur].append({
            "product": cells[0],
            "chemical": cells[1],
            "function": cells[2],
        })

# ---- 5. shop URLs ----
shop = {}
with open(SHOP_CSV, newline="") as f:
    for row in csv.DictReader(f):
        name = (row.get("name") or "").strip()
        url = (row.get("url") or "").strip()
        if not name or not url:
            continue
        shop.setdefault(norm_product(name), url)

matched = unmatched = 0
for sup, items in products.items():
    for p in items:
        url = shop.get(norm_product(p["product"]))
        if url:
            p["url"] = url
            matched += 1
        else:
            unmatched += 1

# ---- 6. validation: every structure supplier must have a products entry ----
struct_suppliers = {s["name"] for r in routes for c in r["children"]
                    for e in c["children"] for s in e["suppliers"]}
missing_products = sorted(struct_suppliers - set(products))

# ---- write ----
(OUT / "excipients.json").write_text(json.dumps(routes, indent=2, ensure_ascii=False) + "\n")
(OUT / "products.json").write_text(json.dumps(products, indent=2, ensure_ascii=False) + "\n")

# ---- report ----
n_routes = len(routes)
n_cats = sum(len(r["children"]) for r in routes)
n_exc = sum(len(c["children"]) for r in routes for c in r["children"])
n_prod = sum(len(v) for v in products.values())
print("=== BUILD SUMMARY ===")
print(f"Routes:      {n_routes}")
print(f"Categories:  {n_cats}")
print(f"Excipients:  {n_exc}  (of which {len(unavailable)} currently unavailable)")
print(f"Suppliers:   {len(products)} sections, {len(struct_suppliers)} referenced in structure")
print(f"Products:    {n_prod}  | shop URLs matched: {matched}, unmatched: {unmatched} ({matched*100//max(n_prod,1)}%)")
print()
print(f"Unavailable excipients ({len(unavailable)}):")
for u in unavailable:
    print("  -", u)
print()
if missing_products:
    print("Suppliers referenced in structure but with NO products section:")
    for m in missing_products:
        print("  -", m)
    print()
if errors:
    print("!!! NAME ERRORS (must fix) !!!")
    for e in sorted(set(errors)):
        print(e)
    sys.exit(1)
print("OK: all supplier names resolved to the canonical list.")
