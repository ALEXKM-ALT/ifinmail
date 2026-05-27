# ifinmail 0.0.1 — Backend App Architecture

**Purpose:** High-level architectural standards and governance for ifinmail applications.  

## 🏗️ Core Architecture

### Application Structure
```
backend/apps/
├── core/           # Foundational capabilities (no external dependencies)

```

**Rule:** `backend/apps` contains `core/` folders.

### App Location Rules
- **Core Apps:** `backend/apps/core/{app_name}/`  
- **Prohibited:** Mixing concerns between layers




### Standard App Structure (Mandatory)
Every app requires:
- **Core Folders:** `admin/`, `migrations/`, `models/`, `serializers/`, `services/`, `views/`, `viewsets/`, `tests/`, `fixtures/`, `forms/`, `types/`, `indexes/`, `mixins/`
- **Core Files:** `api.py`, `apps.py`, `assistant_handlers.py`, `assistant.py`, `web.py`, `urls.py`, `verifications.py`, `preferences.py`, `tasks.py`, `signals.py`, `hooks.py`

## 🔄 Request Flow Contracts

### API Flow
```
api.py → viewsets/ → serializers/ → services/ → models/
```

### Web Flow  
```
web.py → views/ → forms/ → services/ → models/
```

### URL Routing
- **API:** `urls.py → api.py → viewsets → serializers → services → models`
- **Web:** `urls.py → web.py → views → forms → services → models`

## 🛡️ Governance & Requirements

### Mandatory Principles
1. **Services Layer:** Single interface for all model CRUD operations
2. **Strong Typing:** All components must be fully typed
3. **Visibility & Accountability:** Mandatory compliance with base mixins
4. **Architectural Patterns:** Pipeline, adapter, strategy patterns preferred
5. **No Broken Windows:** Quality degradation is never acceptable

### Key Constraints
- **Model Access:** All access must go through `services/` layer
- **Type Safety:** Imports all enums/types from `types/`
- **Core Apps:** Models must inherit from `backend/apps/core/base/models/base.py`
- **services/models.py:** Re-export proxy for intra-app use ONLY. Cross-app imports of `services.models` are FORBIDDEN — import from `models/` or the actual service module directly.
- **CLI Management Commands:** The only exception to cross-layer import rules. CLI-only commands may reference any layer but must include an explanatory comment:
  ```python
  # Architectural exception: CLI developer tooling may import from platform.
  # This is a management command only, never executed at runtime in production.
  ```

## 📦 Storage Architecture (Single Source of Truth)

### Rule: ALL media/files MUST use `backend/apps/core/storage`

**The storage app is the ONLY allowed way to handle media files.**

```
┌────────────────────────────────────────────────────────────┐
│  ❌ FORBIDDEN                    ✅ REQUIRED               │
├────────────────────────────────────────────────────────────┤
│  models.ImageField()            ImageAttachableMixin       │
│  models.FileField()             FileAttachableMixin        │
│  default_storage                StorageService             │
│  upload_to='path/'              StoredFile ForeignKey      │
└────────────────────────────────────────────────────────────┘
```

### Correct Usage Examples

**For single images (logos, thumbnails):**
```python
from backend.apps.core.storage.mixins import ImageAttachableMixin

class Product(ImageAttachableMixin, models.Model):
    name = models.CharField(max_length=200)
    # Access via: product.primary_image, product.image_url
```

**For multiple files/attachments:**
```python
from backend.apps.core.storage.mixins import FileAttachableMixin

class Message(FileAttachableMixin, models.Model):
    content = models.TextField()
    # Access via: message.files.all(), message.images.all()
```

**For explicit file references:**
```python
class DocumentJob(models.Model):
    stored_file = models.ForeignKey(
        "storage.StoredFile",
        on_delete=models.PROTECT,
    )
```

**For file uploads:**
```python
from backend.apps.core.storage.services import StorageService

result = StorageService.upload(
    merchant_id=merchant.id,
    file=uploaded_file,
    user=request.user,
    entity_type='PRODUCT',
    entity_id=product.id,
)
```

# ifinmail - Frontend Design Guide (Remediation)
- Please refer to [DESIGN.md] for any new design or remediation of existing design when checking against compliance requirements for frontend designs.




