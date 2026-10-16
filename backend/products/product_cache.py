"""
Product-specific cache helpers.

Cache-aside logic lives in ProductService; Redis key names live in redis_app.keys.
Keep this module for product-only cache policies if they grow beyond simple get/set.
"""
