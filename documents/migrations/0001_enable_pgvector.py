"""Turn on the pgvector extension inside the database.

This is the foundation every later `vector` column depends on. We use Django's
first-class `CreateExtension` operation (ORM-native, reversible) rather than raw
SQL. Runs before any model migration in this app.
"""

from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        CreateExtension("vector"),
    ]
