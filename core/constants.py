from datetime import timedelta

CLICK_WINDOW = timedelta(hours=24)      # impression -> click / add_to_cart
PURCHASE_WINDOW = timedelta(days=7)     # impression -> purchase

EVENT_TYPES = ("impression", "click", "add_to_cart", "purchase")
REVENUE_KEYS = ("amount", "revenue", "value", "price", "total", "order_value")