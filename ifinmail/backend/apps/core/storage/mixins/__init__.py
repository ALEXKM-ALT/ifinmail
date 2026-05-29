"""Storage mixins — attach file/image capabilities to any model."""

from .file_attachable import FileAttachableMixin
from .image_attachable import ImageAttachableMixin

__all__ = ['FileAttachableMixin', 'ImageAttachableMixin']
