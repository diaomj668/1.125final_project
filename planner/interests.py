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


MEAL_WINDOWS = (("Breakfast", 7*60, 10*60+30), ("Lunch", 11*60+30, 14*60+30), ("Dinner", 17*60+30, 20*60+30))
BREAKFAST_CATEGORIES = {"breakfast restaurant", "brunch restaurant", "bakery", "bagel shop", "cafe", "coffee shop", "donut shop", "diner"}
MAIN_MEAL_CATEGORIES = {"restaurant", "american restaurant", "italian restaurant", "pizza restaurant", "seafood restaurant", "chinese restaurant", "sandwich shop", "fast food restaurant", "bar & grill", "diner"}


def meal_options(business, used_meals):
    cats = {c.casefold() for c in business.categories}
    for name, opening, closing in MEAL_WINDOWS:
        if name in used_meals:
            continue
        allowed = BREAKFAST_CATEGORIES if name == "Breakfast" else MAIN_MEAL_CATEGORIES
        if cats & allowed:
            yield name, opening, closing
