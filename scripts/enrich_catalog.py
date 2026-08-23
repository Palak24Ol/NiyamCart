# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "backend" / "data" / "catalog.json"

MATERIALS: dict[str, list[str]] = {
    "Kurti, Saree & Lehenga": [
        "Cotton Viscose", "Cotton", "Cotton Chikankari", "Rayon Blend", "Silk Blend",
        "Georgette", "Art Silk", "Cotton Blend", "Organza", "Cotton Slub",
    ],
    "Women Western": [
        "Viscose Crepe", "Cotton Blend", "Denim Cotton", "Cotton Elastane", "Cotton Poplin",
        "Polyester Crepe", "Poly Viscose", "Viscose", "Denim Cotton", "Rayon",
    ],
    "Lingerie": [
        "Nylon Elastane", "Cotton Elastane", "Modal Blend", "Cotton Elastane", "Cotton",
        "Satin", "Cotton", "Nylon Elastane", "Cotton Modal", "Fleece",
    ],
    "Men": [
        "Oxford Cotton", "Cotton Blend", "Pique Cotton", "Cotton Twill", "Denim Cotton",
        "Cotton", "Polyester Knit", "Polyester Shell", "Polyester Dry-Fit", "Cotton Twill",
    ],
    "Kids & Toys": [
        "Cotton Blend", "Cotton", "Organic Cotton", "Cotton Jersey", "Cotton Jersey",
        "ABS Plastic", "Wood", "ABS Plastic", "Food-grade Plastic", "Paper and Non-toxic Pigment",
    ],
    "Home & Kitchen": [
        "Cotton", "Stainless Steel", "Borosilicate Glass", "Cotton", "Cotton",
        "Hard-anodised Aluminium", "Stainless Steel", "Carbon Steel", "ABS and Metal", "Microfibre",
    ],
    "Beauty & Health": [
        "Aloe Vera Gel", "Vitamin C Serum", "Amino-acid Cleanser", "Cosmetic Pigment Blend",
        "Herbal Oil Blend", "SPF 50 Cream", "Synthetic Fibre", "Tempered Glass",
        "Polyester Fabric", "ABS and Silicone",
    ],
    "Jewellery & Accessories": [
        "Imitation Pearl and Alloy", "Oxidised Alloy", "Gold-plated Alloy", "Kundan and Alloy",
        "Stainless Steel", "Stainless Steel", "Satin Fabric", "Crystal and Alloy",
        "Acetate Frame", "Polyester Satin",
    ],
    "Bags & Footwear": [
        "PU Leather", "Quilted PU", "Polyester", "Polyester Canvas", "PU Leather",
        "Mesh and EVA", "Engineered Mesh", "Textile and Synthetic Sole", "EVA",
        "Synthetic Leather",
    ],
    "Popular": [
        "Cotton Blend", "Art Silk", "Cotton Jersey", "Rayon Blend", "Food-grade Plastic",
        "PU Leather", "Mesh and EVA", "Kundan and Alloy", "Botanical Skincare Blend",
        "ABS Plastic",
    ],
}


def _family_name(name: str) -> str:
    words = name.split()
    return " ".join(words[1:]) if len(words) > 1 else name


def _specs(item: dict[str, object], family: int) -> dict[str, object]:
    category = str(item["category"])
    name = str(item["name"])
    material = str(item["material"])
    color = str(dict(item["specs"]).get("color_hex", "#66756d"))
    family_name = _family_name(name)
    shared: dict[str, object] = {"product_type": family_name, "color_hex": color}

    if category == "Kurti, Saree & Lehenga":
        return {
            **shared,
            "fabric": material,
            "pattern": ["Floral print", "Block print", "Chikankari", "Embroidered", "Woven", "Bandhani", "Zari embroidered", "Solid with border", "Embellished", "Subtle stripe"][family],
            "silhouette": ["Straight", "A-line", "Straight", "Anarkali", "Saree", "Saree", "Lehenga", "Palazzo set", "Dupatta", "Straight"][family],
            "neckline": ["Round", "Notched", "Boat", "V-neck", "Not applicable", "Not applicable", "Sweetheart", "Round", "Not applicable", "Mandarin"][family],
            "sleeve": ["Three-quarter", "Three-quarter", "Three-quarter", "Full", "Not applicable", "Not applicable", "Sleeveless blouse", "Three-quarter", "Not applicable", "Three-quarter"][family],
            "wash_care": ["Gentle hand wash", "Cold machine wash", "Gentle hand wash", "Dry clean", "Dry clean", "Gentle hand wash", "Dry clean", "Cold machine wash", "Dry clean", "Cold machine wash"][family],
        }
    if category == "Women Western":
        return {
            **shared,
            "fabric": material,
            "fit": ["Wrap fit", "Relaxed", "Wide leg", "Slim", "Oversized", "A-line", "Tailored", "Regular", "Relaxed", "Flowy"][family],
            "length": ["Midi", "Regular", "Full length", "Crop", "Longline", "Midi", "Ankle", "Full length", "Waist", "Maxi"][family],
            "stretch": ["Low", "Low", "Comfort stretch", "High", "Low", "None", "Comfort stretch", "Low", "Low", "Low"][family],
            "closure": ["Tie wrap", "Pull-on", "Button and zip", "Pull-on", "Button", "Side zip", "Hook and zip", "Back zip", "Button", "Pull-on"][family],
            "wash_care": ["Cold machine wash", "Gentle machine wash", "Wash inside out", "Cold wash", "Cold machine wash", "Gentle wash", "Gentle machine wash", "Cold wash", "Wash separately", "Gentle machine wash"][family],
        }
    if category == "Lingerie":
        return {
            **shared,
            "fabric": material,
            "support": ["Medium", "Medium", "Light", "Not applicable", "Not applicable", "Relaxed", "Relaxed", "Firm", "Medium", "Relaxed"][family],
            "padding": ["Lightly padded", "Padded", "Non-padded", "Not applicable", "Not applicable", "Not applicable", "Not applicable", "Non-padded", "Non-padded", "Not applicable"][family],
            "wire": ["Wirefree", "Wirefree", "Wirefree", "Not applicable", "Not applicable", "Not applicable", "Not applicable", "Wirefree", "Wirefree", "Not applicable"][family],
            "closure": ["Back hook", "Back hook", "Pull-on", "Pull-on", "Pull-on", "Button", "Drawstring", "Pull-on", "Front opening", "Tie belt"][family],
            "wash_care": "Hand wash separately",
        }
    if category == "Men":
        return {
            **shared,
            "fabric": material,
            "fit": ["Regular", "Slim", "Regular", "Relaxed", "Straight", "Regular", "Tapered", "Regular", "Athletic", "Slim"][family],
            "collar_or_waist": ["Button-down", "Spread collar", "Polo collar", "Elastic drawstring", "Mid rise", "Mandarin", "Elastic drawstring", "Ribbed collar", "Crew neck", "Mid rise"][family],
            "sleeve_or_length": ["Full sleeve", "Full sleeve", "Half sleeve", "Full length", "Full length", "Full sleeve", "Full length", "Full sleeve", "Half sleeve", "Full length"][family],
            "pattern": ["Oxford weave", "Solid", "Solid", "Utility", "Denim", "Solid", "Colour block", "Solid", "Performance knit", "Solid"][family],
            "wash_care": "Machine wash cold",
        }
    if category == "Kids & Toys":
        return {
            **shared,
            "primary_material": material,
            "recommended_age": ["4–8 years", "3–8 years", "0–18 months", "3–10 years", "3–10 years", "6+ years", "2–5 years", "18+ months", "3–7 years", "5+ years"][family],
            "key_feature": ["Soft lining", "Comfort waistband", "Nickel-free snaps", "Breathable knit", "Tag-free neck", "120 pieces", "Non-toxic paint", "Volume control", "Rounded edges", "Reusable supplies"][family],
            "safety": ["Skin-safe dyes", "Skin-safe dyes", "Baby-safe fabric", "Skin-safe dyes", "Skin-safe dyes", "BIS-aligned parts", "Non-toxic finish", "BIS-aligned electronics", "Rounded components", "Non-toxic colours"][family],
            "care": ["Gentle wash", "Gentle wash", "Machine wash", "Machine wash", "Machine wash", "Wipe clean", "Wipe clean", "Wipe clean", "Wipe clean", "Store dry"][family],
        }
    if category == "Home & Kitchen":
        return {
            **shared,
            "primary_material": material,
            "size_or_capacity": ["Double bed · 228 × 254 cm", "5-piece set", "6 × 750 ml", "70 × 140 cm", "40 × 40 cm · pack of 5", "26 cm", "1 litre", "3-tier", "42 cm height", "45 × 75 cm · pack of 2"][family],
            "key_feature": ["144 thread count", "Induction compatible", "Airtight silicone seal", "High absorbency", "Concealed zipper", "PFOA-free coating", "12-hour temperature retention", "Rust-resistant", "Three brightness modes", "Anti-skid backing"][family],
            "care": ["Machine wash", "Dishwasher safe", "Top-rack dishwasher safe", "Machine wash", "Machine wash", "Hand wash", "Hand wash", "Wipe clean", "Dry cloth only", "Machine wash"][family],
            "warranty": ["Manufacturing defects", "12 months", "6 months", "Manufacturing defects", "Manufacturing defects", "12 months", "12 months", "6 months", "12 months", "Manufacturing defects"][family],
        }
    if category == "Beauty & Health":
        return {
            **shared,
            "form_factor": ["Gel", "Serum", "Foam", "Liquid colour", "Oil", "Cream", "Brush set", "Digital device", "Electric pad", "Manual roller"][family],
            "suitable_for": ["All skin types", "Normal to oily skin", "Sensitive skin", "All skin tones", "All hair types", "All skin types", "Face and eye makeup", "Home wellness tracking", "Targeted heat therapy", "Muscle relaxation"][family],
            "key_feature": ["Aloe and hyaluronic acid", "10% vitamin C", "pH-balanced cleanser", "Transfer-resistant", "Herbal blend", "Broad-spectrum SPF 50", "Synthetic soft bristles", "Tempered glass platform", "Three heat levels", "Textured pressure points"][family],
            "quantity_or_size": ["100 ml", "30 ml", "100 ml", "Set of 4", "200 ml", "50 g", "Set of 8", "30 × 30 cm", "30 × 20 cm", "16 cm"][family],
            "use_guidance": ["Patch test first", "Use sunscreen during daytime", "Use twice daily", "External use only", "Massage into scalp", "Reapply every two hours", "Clean after use", "Use on a flat surface", "Do not sleep while in use", "Avoid injured areas"][family],
        }
    if category == "Jewellery & Accessories":
        return {
            **shared,
            "base_material": material,
            "finish": ["Pearl finish", "Oxidised", "High polish", "Kundan", "Minimal polish", "Brushed metal", "Printed fabric", "Crystal set", "UV400", "Silk-touch weave"][family],
            "closure": ["Push back", "Fish hook", "Lobster clasp", "Adjustable tie", "Stretch", "Buckle", "Elastic", "Snap clip", "Hinged temple", "Free drape"][family],
            "size": ["4.5 cm drop", "6 cm drop", "45–52 cm", "30–38 cm", "Set of 5", "38 mm dial", "Pack of 6", "Pack of 4", "Medium frame", "180 × 70 cm"][family],
            "care": ["Keep dry", "Keep dry", "Store flat", "Store in pouch", "Avoid perfume", "Wipe with soft cloth", "Hand wash", "Wipe clean", "Use lens cloth", "Gentle hand wash"][family],
        }
    if category == "Bags & Footwear":
        return {
            **shared,
            "primary_material": material,
            "closure": ["Magnetic snap", "Zip", "Dual zip", "Dual zip", "Flap and zip", "Lace-up", "Lace-up", "Slip-on", "Slip-on", "Buckle"][family],
            "size_or_capacity": ["34 × 28 × 12 cm", "24 × 18 × 8 cm", "22 litres", "38 litres", "Fits 15.6-inch laptop", "Women UK 4–8", "Men UK 6–11", "Women UK 4–8", "UK 4–9", "Women UK 4–8"][family],
            "key_feature": ["Reinforced handles", "Adjustable strap", "Padded laptop sleeve", "Shoe compartment", "Padded organiser", "Memory-foam sockliner", "Cushioned heel", "Padded footbed", "Textured sole", "Stable block heel"][family],
            "water_resistance": ["Splash resistant", "Splash resistant", "Water resistant", "Water resistant", "Water resistant", "Light splash", "Light splash", "No", "Water friendly", "No"][family],
            "care": "Wipe clean with a soft cloth",
        }
    return {
        **shared,
        "primary_material": material,
        "use_case": str(item["occasion"]),
        "featured_attribute": ["Trending style", "Bestseller", "Relaxed fit", "Coordinated set", "Space saving", "Hands-free carry", "Cushioned comfort", "Festive finish", "Daily skincare", "Creative learning"][family],
        "selection_basis": "High catalogue rating and verified availability",
        "care": "Follow the product label guidance",
    }


def main() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    category_offsets: dict[str, int] = {}
    for item in catalog:
        category = str(item["category"])
        offset = category_offsets.get(category, 0)
        family = min(offset // 5, 9)
        material = MATERIALS[category][family]
        item["material"] = material
        family_name = _family_name(str(item["name"]))
        occasion = str(item["occasion"]).lower()
        item["description"] = (
            f"Designed for {occasion}, this {family_name.lower()} uses {material.lower()} for "
            "value-conscious Indian shoppers. Clear specifications, verified media and seller "
            "evidence make it ready for an informed purchase."
        )
        highlights = list(item["highlights"])
        highlights[0] = f"{material} construction with product-specific care guidance"
        item["highlights"] = highlights
        item["specs"] = _specs(item, family)
        item["version"] = max(int(item.get("version", 1)), 3)
        category_offsets[category] = offset + 1
    CATALOG_PATH.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Enriched {len(catalog)} products with category-specific specifications")


if __name__ == "__main__":
    main()
