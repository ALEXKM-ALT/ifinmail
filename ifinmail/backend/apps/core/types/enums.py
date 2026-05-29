from enum import StrEnum


class EntityType(StrEnum):
    """Entity types for StoredFile association (AGENTS.md § Storage)."""

    PRODUCT = 'PRODUCT'
    USER = 'USER'
    MESSAGE = 'MESSAGE'
    DOCUMENT = 'DOCUMENT'


class StorageVisibility(StrEnum):
    """Visibility levels for stored files."""

    PRIVATE = 'PRIVATE'
    INTERNAL = 'INTERNAL'
    PUBLIC = 'PUBLIC'


__all__ = ['EntityType', 'StorageVisibility']
