from __future__ import unicode_literals

from django.db import migrations

DEFAULT_CATEGORIES = [
    'Connectivity', 'Development', 'Games', 'Graphics', 'Internet', 'Money', 'Multimedia',
    'Navigation', 'Phone & SMS', 'Reading', 'Science & Education', 'Security', 'Sports & Health',
    'System', 'Theming', 'Time', 'Writing'
]


def forwards_func(apps, schema_editor):
    # noinspection PyPep8Naming
    Category = apps.get_model("repomaker", "Category")
    db_alias = schema_editor.connection.alias
    Category.objects.using(db_alias).bulk_create(
        [Category(user=None, name=name) for name in DEFAULT_CATEGORIES])


def reverse_func(apps, schema_editor):
    # noinspection PyPep8Naming
    Category = apps.get_model("repomaker", "Category")
    db_alias = schema_editor.connection.alias
    for name in DEFAULT_CATEGORIES:
        Category.objects.using(db_alias).filter(user=None, name=name).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('repomaker', 'default_user'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
