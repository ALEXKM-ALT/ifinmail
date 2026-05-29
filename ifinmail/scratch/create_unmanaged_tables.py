# ruff: noqa: E402
import os
from unittest.mock import patch

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.development')
django.setup()

from django.db import connection

from backend.apps.dns.models import DNSProviderConfig
from backend.apps.domains.models import DKIMKey, Domain
from backend.apps.mail.models import Alias, Mailbox

models = [Domain, DKIMKey, Mailbox, Alias, DNSProviderConfig]

for model in models:
    db_table = model._meta.db_table
    if db_table in connection.introspection.table_names():
        print(f"Table '{db_table}' already exists.")
        continue
    print(f"Creating table for {model.__name__} ('{db_table}')...")
    try:
        with (
            patch.object(model._meta, 'managed', True),
            connection.schema_editor(atomic=False) as schema_editor,
        ):
            schema_editor.create_model(model)
        print(f"Created table '{db_table}'.")
    except Exception as e:
        print(f"Error creating table '{db_table}': {e}")
