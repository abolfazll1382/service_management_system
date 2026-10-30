"""PostgreSQL extensions the schema depends on.

``pg_trgm`` powers the trigram GIN indexes that make the work-queue's ``icontains`` search
(tracking code, national ID, phone, applicant name) fast without a full-text engine. It is a
*trusted* extension since PostgreSQL 13, so the database owner can create it without superuser.
"""

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [TrigramExtension()]
