import datetime
import os

from django.conf import settings

TEST_DIR = os.path.join(settings.BASE_DIR, 'test_dir')
TEST_FILES_DIR = os.path.join(settings.BASE_DIR, 'tests')


def datetime_is_recent(dt, seconds=10 * 60):
    now = datetime.datetime.utcnow().timestamp()
    return now - seconds < dt.timestamp() < now
