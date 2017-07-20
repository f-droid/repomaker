import os
import sys

# The name of the default user. Please DO NOT CHANGE
DEFAULT_USER_NAME = 'user'


def runserver():
    execute([sys.argv[0], 'migrate'])
    if len(sys.argv) <= 1 or sys.argv[1] != 'runserver':
        sys.argv = sys.argv[:1] + ['runserver'] + sys.argv[1:]
    execute(sys.argv)


def process_tasks():
    if len(sys.argv) <= 1 or sys.argv[1] != 'process_tasks':
        sys.argv = sys.argv[:1] + ['process_tasks'] + sys.argv[1:]
    execute(sys.argv)


def execute(params):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "repomaker.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise
    execute_from_command_line(params)
