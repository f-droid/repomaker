from pkg_resources import Requirement, resource_filename
from repomaker.settings import *  # pylint: disable=wildcard-import,unused-wildcard-import


# Where user data such as repositories will be stored
DATA_DIR = os.path.join(os.path.expanduser('~'), '.local', 'share', 'repomaker')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(DATA_DIR, 'db.sqlite3'),
    }
}

# Location for media accessible via the web-server such as repo icons, screenshots, etc.
MEDIA_ROOT = os.path.join(DATA_DIR, 'media')

# Location for private data such as the repo signing key
PRIVATE_REPO_ROOT = os.path.join(DATA_DIR, 'private_repo')

# Static repomaker files (CSS, JavaScript, Images)
STATIC_ROOT = resource_filename(Requirement.parse("repomaker"), "repomaker-static")
NODE_MODULES_ROOT = os.path.join(STATIC_ROOT, 'node_modules')

STATICFILES_DIRS = [
    ('node_modules', NODE_MODULES_ROOT),
]

# Do not try to compile SASS files
SASS_PROCESSOR_ENABLED = False

JS_REVERSE_JS_MINIFY = True
COMPRESS_OFFLINE = True
