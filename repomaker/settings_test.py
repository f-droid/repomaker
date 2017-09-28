from repomaker.settings import *  # pylint: disable=wildcard-import,unused-wildcard-import


TEST_FILES_DIR = os.path.join(BASE_DIR, 'tests')

TEST_DIR = os.path.join(BASE_DIR, 'test_dir')
MEDIA_ROOT = os.path.join(TEST_DIR, 'media')
PRIVATE_REPO_ROOT = os.path.join(TEST_DIR, 'private_repo')
STATIC_ROOT = os.path.join(TEST_DIR, 'static')

SINGLE_USER_MODE = True

COMPRESS_ENABLED = False
