from enum import Enum


class EntityType(str, Enum):
    """Entity types for StoredFile association (AGENTS.md § Storage)."""
    PRODUCT = "PRODUCT"
    USER = "USER"
    MESSAGE = "MESSAGE"
    DOCUMENT = "DOCUMENT"


class StorageVisibility(str, Enum):
    """Visibility levels for stored files."""
    PRIVATE = "PRIVATE"
    INTERNAL = "INTERNAL"
    PUBLIC = "PUBLIC"


__all__ = ["EntityType", "StorageVisibility"]
