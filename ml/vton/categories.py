"""Image-generation categories, deliberately separate from size-chart coverage."""
from enum import Enum


class GarmentCategory(str, Enum):
    tshirt = "t-shirt"
    shirt = "shirt"
    blouse = "blouse"
    sweater = "sweater"
    jacket = "jacket"
    trouser = "trouser"
    jeans = "jeans"
    shorts = "shorts"
    skirt = "skirt"
    dress = "dress"
    jumpsuit = "jumpsuit"


MODEL_CATEGORIES = {
    "t-shirt": "tops", "shirt": "tops", "blouse": "tops", "sweater": "tops",
    "jacket": "tops", "trouser": "bottoms", "jeans": "bottoms", "shorts": "bottoms",
    "skirt": "bottoms", "dress": "one-pieces", "jumpsuit": "one-pieces",
}
