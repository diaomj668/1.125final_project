"""Map user interests to Google Local category names, and visit lengths.

Category names must match the 'category' field in the metadata exactly
(case-insensitive). Edit these lists to change what an interest means.
"""

INTEREST_CATEGORIES = {
    "food": [
        "Restaurant", "American restaurant", "Italian restaurant", "Pizza restaurant",
        "Breakfast restaurant", "Seafood restaurant", "Chinese restaurant",
        "Sandwich shop", "Bakery", "Bagel shop", "Ice cream shop", "Donut shop",
        "Cafe", "Coffee shop",
    ],
    "culture": [
        "Museum", "Art museum", "History museum", "Art gallery",
        "Historical landmark", "Tourist attraction", "Library",
    ],
    "outdoors": [
        "Park", "Beach", "Hiking area", "Nature preserve", "Garden", "Botanical garden",
    ],
    "shopping": [
        "Clothing store", "Women's clothing store", "Men's clothing store",
        "Gift shop", "Shoe store",
    ],
    "nightlife": [
        "Bar", "Bar & grill", "Brewery", "Cocktail bar", "Pub",
    ],
}

# Typical visit length in minutes, per interest.
VISIT_MINUTES = {"food": 60, "culture": 90, "outdoors": 60, "shopping": 45, "nightlife": 75}

INTEREST_NAMES = tuple(INTEREST_CATEGORIES)


def interests_for(business, wanted):
    """Interests (from `wanted`) that this business's categories match."""
    cats = {c.lower() for c in business.categories}
    return tuple(i for i in wanted
                 if any(c.lower() in cats for c in INTEREST_CATEGORIES[i]))


def visit_minutes(interest):
    return VISIT_MINUTES[interest]
