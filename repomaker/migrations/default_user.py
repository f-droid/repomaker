from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations

from repomaker import DEFAULT_USER_NAME


def forwards_func(apps, schema_editor):
    if not settings.SINGLE_USER_MODE:
        return
    # noinspection PyPep8Naming
    User = apps.get_model("auth", "User")
    db_alias = schema_editor.connection.alias
    User.objects.using(db_alias).create(username=DEFAULT_USER_NAME, is_staff=True,
                                        is_superuser=True)


def reverse_func(apps, schema_editor):
    if not settings.SINGLE_USER_MODE:
        return
    # noinspection PyPep8Naming
    User = apps.get_model("auth", "User")
    db_alias = schema_editor.connection.alias
    User.objects.using(db_alias).filter(username=DEFAULT_USER_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('repomaker', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
