WEIGHTS = {
    "shoulder_width": 0.20,
    "chest_circumference": 0.25,
    "waist_circumference": 0.20,
    "hip_circumference": 0.20,
    "thigh_circumference": 0.10,
    "inseam_length": 0.05,
}
METRICS = tuple(WEIGHTS)
TOP_METRICS = METRICS[:4]
BOTTOM_METRICS = METRICS[2:]
CATEGORY_METRICS = {
    **dict.fromkeys(("t-shirt", "shirt", "blouse", "sweater", "jacket", "dress", "kurta", "kurti", "salwar-suit", "blazer"), TOP_METRICS),
    **dict.fromkeys(("trouser", "jeans", "shorts", "skirt", "leggings"), BOTTOM_METRICS),
    "jumpsuit": METRICS,
}
# Skirts do not depend on leg length or individual thigh circumference.
CATEGORY_METRICS["skirt"] = ("waist_circumference", "hip_circumference")
