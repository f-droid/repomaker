import os
import sys

from django.core.checks import Error, register
from fdroidserver import common
from fdroidserver.exception import FDroidException

VERSION = '1.0.0b2'

# The name of the default user. Please DO NOT CHANGE
DEFAULT_USER_NAME = 'user'


def runserver():
    execute([sys.argv[0], 'migrate'])  # TODO move into package hook?
    if len(sys.argv) <= 1 or sys.argv[1] != 'runserver':
        sys.argv = sys.argv[:1] + ['runserver'] + sys.argv[1:]
    sys.argv.append('--noreload')
    execute(sys.argv)


def process_tasks():
    if len(sys.argv) <= 1 or sys.argv[1] != 'process_tasks':
        sys.argv = sys.argv[:1] + ['process_tasks'] + sys.argv[1:]
    execute(sys.argv)


def execute(params):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "repomaker.settings_desktop")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        # The above import may fail for some other reason. Ensure that the
        # issue is really that Django is missing to avoid masking other
        # exceptions on Python 2.
        try:
            import django  # pylint: disable=unused-import
        except ImportError:
            raise ImportError(
                "Couldn't import Django. Are you sure it's installed and "
                "available on your PYTHONPATH environment variable? Did you "
                "forget to activate a virtual environment?"
            )
        raise

    # create DATA_DIR if it doesn't exist
    from django.conf import settings
    if not os.path.isdir(settings.DATA_DIR):
        os.makedirs(settings.DATA_DIR)

    if len(sys.argv) > 1 and sys.argv[1] == 'process_tasks':
        non_atomic_background_tasks()

    # execute pending command
    execute_from_command_line(params)


def non_atomic_background_tasks():
    from django import setup
    setup()
    import background_task.tasks
    from repomaker.tasks import DesktopRunner
    background_task.tasks.tasks._runner = DesktopRunner()  # pylint: disable=protected-access


@register()
def requirements_check(app_configs, **kwargs):  # pylint: disable=unused-argument
    errors = []
    config = {}
    common.fill_config_defaults(config)
    common.config = config
    if 'keytool' not in config:
        errors.append(
            Error(
                'Could not find `keytool` program.',
                hint='This program usually comes with Java. Try to install JRE. '
                     'On Debian-based system you can try to run '
                     '`apt install default-jre-headless`.',
            )
        )
    if 'jarsigner' not in config and not common.set_command_in_config('apksigner'):
        errors.append(
            Error(
                'Could not find `jarsigner` or `apksigner`. At least one of them is required.',
                hint='Please install the missing tool. On Debian-based systems you can try to run '
                     '`apt install apksigner`.',
            )
        )
    # rsync
    if common.find_command('rsync') is None:
        errors.append(
            Error(
                'Could not find `rsync` program.',
                hint='Please install it before continuing. On Debian-based systems you can run '
                     '`apt install rsync`.',
            )
        )
    # git
    if common.find_command('git') is None:
        errors.append(
            Error(
                'Could not find `git` program.',
                hint='Please install it before continuing. On Debian-based systems you can run '
                     '`apt install git`.',
            )
        )
    return errors
