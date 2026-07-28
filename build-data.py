#!/usr/bin/env python3
"""
Regenerate excipients.json (stages 2-5) and products.json (stage 6) for the
Excipient Sourcing Navigator from the source files in
ea-work/data-for-reoccurring-tasks/.

Sources (v2 pipeline, 2026-07-27):
  - excipients-landscape-structure-v2.md  -> route (#) > category (##) > excipient (-)
  - excipient-products-tree.md            -> excipient (##) > supplier (###) > product bullets
  - supplier-page-urls.md                 -> supplier -> PharmaExcipients supplier page URL

The product tree carries everything stage 6 needs, including the e-shop links,
so the old shop CSV matching and the per-supplier products file are no longer
part of the build.

Product bullet format expected in the tree:
  - Product name — chemical/generic name — [n] involvement tag — function → [Shop label](url), [...]

Run from the project folder: python3 build-data.py
"""
import json
import os
import re
import sys
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

# Source files live in ea-work/data-for-reoccurring-tasks, two levels up from this
# project folder. Resolved relative to this script so it works on any machine.
# Override with the PE_DATA_DIR environment variable if your layout differs.
DATA = Path(os.environ.get(
    "PE_DATA_DIR",
    Path(__file__).resolve().parents[2] / "data-for-reoccurring-tasks",
))
OUT = Path(__file__).parent

STRUCT_MD = DATA / "excipients-landscape-structure-v2.md"
TREE_MD = DATA / "excipient-products-tree.md"
URLS_MD = DATA / "supplier-page-urls.md"

# Supplier sections in the tree that must never reach the tool.
EXCLUDED_SUPPLIERS = {"Unknown Supplier"}

# Same company written two ways in the tree. Left side maps to the canonical
# spelling on the right (the spelling the tool displays).
SUPPLIER_ALIASES = {
    "ShinEtsu": "Shin-Etsu",
    "Sudzucker": "Südzucker AG",
}

# Excipient sections in the tree with no home in the route/category taxonomy.
EXCLUDED_EXCIPIENTS = {"Unclassified"}

# Involvement tag -> short label shown on the product card, and whether the
# excipient is a primary part of the product (drives the stage 6 grouping).
TAGS = {
    1: ("sole substance", True),
    2: ("form / grade variant", True),
    3: ("co-processed, primary component", True),
    4: ("co-processed, minor component", False),
    5: ("carrier / substrate", False),
    6: ("formulated system", False),
}

BULLET_RE = re.compile(r"^\[(\d)\]")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")

warnings = []


def sort_key(name):
    """Alphabetical key for everything the tool renders as a button.

    Case-insensitive and accent-folded, so "Südzucker AG" files under S-u-d
    rather than after every z. The source files list things in their own
    editorial order, which is not alphabetical; this is what makes the tool's
    order independent of that.
    """
    decomposed = unicodedata.normalize("NFD", name)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def norm_supplier(name):
    """Normalize a supplier name for matching across files."""
    n = name.lower().replace("ü", "u").replace("ö", "o").replace("ä", "a")
    n = re.sub(r"\([^)]*\)", "", n)          # drop parentheticals e.g. (LLS Health)
    return re.sub(r"[^a-z0-9]+", "", n)      # punctuation and spaces out entirely


def canonical(name):
    return SUPPLIER_ALIASES.get(name, name)


# ---- 1. supplier page URLs ----
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
    # Key on the canonical spelling so a row written the other way round
    # (e.g. "Sudzucker" for "Südzucker AG") still resolves.
    supplier_url[norm_supplier(canonical(company))] = url


def page_url(supplier):
    """Supplier page URL, or None when the supplier has no portal page."""
    return supplier_url.get(norm_supplier(supplier))


# ---- 2. product tree: excipient > supplier > products ----
tree = OrderedDict()
excipient = supplier = None
dupes = 0
malformed = []

for lineno, raw in enumerate(TREE_MD.read_text().splitlines(), 1):
    line = raw.rstrip()
    if line.startswith("## ") and not line.startswith("### "):
        excipient = line[3:].strip()
        tree.setdefault(excipient, OrderedDict())
        supplier = None
    elif line.startswith("### ") and excipient:
        supplier = canonical(line[4:].strip())
        tree[excipient].setdefault(supplier, [])
    elif line.startswith("- ") and excipient and supplier:
        body = line[2:].strip()
        head, _, tail = body.partition(" → ")
        links = [{"label": lbl.strip(), "url": url}
                 for lbl, url in LINK_RE.findall(tail)] if tail else []
        fields = [f.strip() for f in head.split(" — ")]
        if len(fields) != 4 or not BULLET_RE.match(fields[2]):
            malformed.append(f"  L{lineno}: {excipient} > {supplier} | {body[:110]}")
            continue
        name, chemical, tag_raw, function = fields
        tag = int(BULLET_RE.match(tag_raw).group(1))
        label, primary = TAGS[tag]
        entry = {
            "product": name,
            "chemical": chemical,
            "tag": tag,
            "tagLabel": label,
            "primary": primary,
            "function": function,
            "links": links,
        }
        bucket = tree[excipient][supplier]
        # Collapse bullets that repeat verbatim within one excipient > supplier
        # section, merging their shop links.
        twin = next((e for e in bucket
                     if (e["product"], e["chemical"], e["tag"], e["function"])
                     == (name, chemical, tag, function)), None)
        if twin:
            seen = {l["url"] for l in twin["links"]}
            twin["links"].extend(l for l in links if l["url"] not in seen)
            dupes += 1
        else:
            bucket.append(entry)

# Drop excluded suppliers and any section left empty by the exclusions.
for exc in list(tree):
    for sup in list(tree[exc]):
        if sup in EXCLUDED_SUPPLIERS or not tree[exc][sup]:
            del tree[exc][sup]
for exc in EXCLUDED_EXCIPIENTS:
    tree.pop(exc, None)

# Stage 6 order: excipient-is-primary products first, minor and derivative
# after, and alphabetical inside each of those two groups.
for exc, sups in tree.items():
    for sup, items in sups.items():
        items.sort(key=lambda e: (0 if e["primary"] else 1, sort_key(e["product"])))

# ---- 3. structure: routes > categories > excipients ----
routes = []
route = cat = None
for raw in STRUCT_MD.read_text().splitlines():
    line = raw.rstrip()
    if line.startswith("# ") and not line.startswith("## "):
        route = {"name": line[2:].strip(), "children": []}
        routes.append(route)
        cat = None
    elif line.startswith("## ") and route is not None:
        cat = {"name": line[3:].strip(), "children": []}
        route["children"].append(cat)
    elif line.startswith("- ") and cat is not None:
        name = line[2:].strip()
        suppliers = [{"name": s, "link": page_url(s)}
                     for s in sorted(tree.get(name, {}), key=sort_key)]
        cat["children"].append({"name": name, "suppliers": suppliers})

# The file's own title is an H1 too; it collects no categories, so it drops out.
routes = [r for r in routes if r["children"]]

# Categories, excipients, suppliers, and products are alphabetical, regardless of
# the order the source files happen to use.
#
# Routes are the deliberate exception: they keep the structure file's own order,
# which ranks them by relevance rather than by name. Stage 2 gives the first one
# a full-width card, so whichever route leads this list is the one that gets it.
# Reordering the H1 headings in excipients-landscape-structure-v2.md is how you
# change either.
for r in routes:
    r["children"].sort(key=lambda c: sort_key(c["name"]))
    for c in r["children"]:
        c["children"].sort(key=lambda e: sort_key(e["name"]))

# ---- 4. validation ----
struct_names = {e["name"] for r in routes for c in r["children"] for e in c["children"]}
unavailable = sorted(n for n in struct_names if not tree.get(n))
orphans = sorted(set(tree) - struct_names)
for o in orphans:
    warnings.append(f"  tree excipient with no place in the taxonomy: {o}")
for m in malformed:
    warnings.append(m)

# products.json only needs excipients the taxonomy can actually reach. Keys are
# sorted too: stage 6 looks products up by key so order does not reach the
# screen, but it keeps the generated file's diffs readable.
products = OrderedDict(
    (e, OrderedDict(sorted(tree[e].items(), key=lambda kv: sort_key(kv[0]))))
    for e in sorted(tree, key=sort_key) if e in struct_names and tree[e])

# ---- write ----
(OUT / "excipients.json").write_text(
    json.dumps(routes, indent=2, ensure_ascii=False) + "\n")
(OUT / "products.json").write_text(
    json.dumps(products, indent=2, ensure_ascii=False) + "\n")

# ---- report ----
n_cats = sum(len(r["children"]) for r in routes)
n_slots = len(struct_names and [e for r in routes for c in r["children"] for e in c["children"]])
all_sup = sorted({s for v in products.values() for s in v}, key=sort_key)
no_page = [s for s in all_sup if not page_url(s)]
n_prod = sum(len(i) for v in products.values() for i in v.values())
n_linked = sum(1 for v in products.values() for i in v.values() for p in i if p["links"])
n_primary = sum(1 for v in products.values() for i in v.values() for p in i if p["primary"])

print("=== BUILD SUMMARY ===")
print(f"Routes:      {len(routes)}")
print(f"Categories:  {n_cats}")
print(f"Excipients:  {len(struct_names)} distinct in {n_slots} route/category slots "
      f"({len(unavailable)} with no supplier)")
print(f"Suppliers:   {len(all_sup)}  ({len(no_page)} without a portal page, shown without the Supplier Page button)")
print(f"Products:    {n_prod}  | with e-shop link: {n_linked} ({n_linked * 100 // max(n_prod, 1)}%)"
      f" | excipient is primary: {n_primary}, minor or derived: {n_prod - n_primary}")
if dupes:
    print(f"Duplicates:  {dupes} repeated bullets collapsed")
print()
print(f"Suppliers without a portal page ({len(no_page)}):")
for s in no_page:
    print("  -", s)
print()
print(f"Excipients with no supplier, shown as currently unavailable ({len(unavailable)}):")
for u in unavailable:
    print("  -", u)
print()
if warnings:
    print("!!! WARNINGS !!!")
    for w in warnings:
        print(w)
    sys.exit(1)
print("OK: every product bullet parsed, every excipient placed.")
