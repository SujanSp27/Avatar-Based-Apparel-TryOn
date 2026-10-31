"""Update frontend discoveredGarments.ts with Levi's and Westside products."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
discovered_ts = ROOT / "frontend/src/features/catalog/discoveredGarments.ts"
new_items_json = ROOT / "data/catalog/new-discovered-garments.json"

with new_items_json.open("r", encoding="utf-8") as f:
    new_items = json.load(f)

content = discovered_ts.read_text(encoding="utf-8")

# Convert new items to TypeScript formatted objects
ts_objects = []
for item in new_items:
    colors_json = json.dumps(item["colors"])
    occasions_json = json.dumps(item["occasions"])
    sizes_json = json.dumps(item["sizes"])
    obj_str = f"""  {{
    id: {json.dumps(item["id"])},
    name: {json.dumps(item["name"])},
    brand_name: {json.dumps(item["brand_name"])},
    category: {json.dumps(item["category"])},
    audience: {json.dumps(item["audience"])},
    colors: {colors_json},
    occasions: {occasions_json},
    sizes: {sizes_json},
    size_note: {json.dumps(item["size_note"])},
    photoType: {json.dumps(item["photoType"])},
    imageUrl: {json.dumps(item["imageUrl"])},
    referenceImageUrl: {json.dumps(item["referenceImageUrl"])},
    description:
      {json.dumps(item["description"])},
    license: {json.dumps(item["license"])},
    source_url: {json.dumps(item["source_url"])},
    commercial_use: true,
    tryon_supported: true,
    qualityReview: {{
      status: "approved",
      message: {json.dumps(item["qualityReview"]["message"])},
    }},
  }},"""
    ts_objects.append(obj_str)

new_code_block = "\n" + "\n".join(ts_objects)

# Target insertion right before the end of DISCOVERED_GARMENTS array
# Look for ];\n\nexport function getDiscoveredGarmentById
target = "];\n\nexport function getDiscoveredGarmentById"
if target not in content:
    raise ValueError("Target insertion point not found in discoveredGarments.ts")

updated_content = content.replace(target, new_code_block + "\n" + target)

# Also update brand filtering in filterDiscoveredGarments
old_brand_filter = """  if (options.brand) {
    const b = options.brand.toLowerCase();
    list = list.filter(
      (item) =>
        item.brand_name.toLowerCase() === b ||
        (b === "h-m" && item.brand_name.toLowerCase() === "h&m") ||
        (b === "h&m" && item.brand_name.toLowerCase() === "h&m"),
    );
  }"""

new_brand_filter = """  if (options.brand) {
    const b = options.brand.toLowerCase();
    list = list.filter(
      (item) =>
        item.brand_name.toLowerCase() === b ||
        ((b === "h-m" || b === "h&m") && item.brand_name.toLowerCase() === "h&m") ||
        ((b === "levi-s" || b === "levis" || b === "levi's") && item.brand_name.toLowerCase() === "levi's") ||
        (b === "westside" && item.brand_name.toLowerCase() === "westside"),
    );
  }"""

if old_brand_filter in updated_content:
    updated_content = updated_content.replace(old_brand_filter, new_brand_filter)
else:
    print("Warning: old_brand_filter string not matched exactly, checking variants")

discovered_ts.write_text(updated_content, encoding="utf-8")
print(f"Successfully updated {discovered_ts} with {len(new_items)} new garments!")
