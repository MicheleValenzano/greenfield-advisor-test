import os

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8001")
IMAGE_SERVICE_URL = os.getenv("IMAGE_SERVICE_URL", "http://image-service:8003")
FIELD_SERVICE_URL = os.getenv("FIELD_SERVICE_URL", "http://field-service:8004")
INTELLIGENT_SERVICE_URL = os.getenv("INTELLIGENT_SERVICE_URL", "http://intelligent-service:8005")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "ws://notification-service:8006")

REDIS_URL = os.getenv("REDIS_URL", "redis://redis-api-gateway:6379")

ROUTE_MAP = {
    # auth-service
    "/login": "auth",
    "/register": "auth",
    "/users": "auth",

    # field-service
    "/fields": "field",
    "/sensor-types": "field",

    # image-service
    "/compute-ndvi": "image",

    # intelligent-service
    "/rules": "intelligent",
    "/archive-alerts": "intelligent",
    "/alerts": "intelligent",
    "/ai-prediction": "intelligent",

    # notifications-service
    "/ws/notifications": "notifications",
}

SERVICE_URLS = {
    "auth": AUTH_SERVICE_URL,
    "field": FIELD_SERVICE_URL,
    "image": IMAGE_SERVICE_URL,
    "intelligent": INTELLIGENT_SERVICE_URL,
    "notifications": NOTIFICATION_SERVICE_URL,
}

PUBLIC_PATHS = {
    "/login",
    "/register",
}