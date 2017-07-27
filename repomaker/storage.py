import os
import re

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from repomaker.utils import to_universal_language_code

REPO_DIR = 'repo'

USER_RE = re.compile('^user_([0-9]+)$')
REMOTE_REPO_RE = re.compile('^remote_repo_([0-9]+)$')


def get_repo_file_path(repo, filename):
    if hasattr(repo, 'user'):
        return os.path.join(get_repo_path(repo), filename)
    else:
        return os.path.join(get_remote_repo_path(repo), filename)


def get_repo_root_path(repo):
    return os.path.join('user_{0}'.format(repo.user.pk), 'repo_{0}'.format(repo.pk))


def get_repo_path(repo):
    return os.path.join(get_repo_root_path(repo), REPO_DIR)


def get_remote_repo_path(repo):
    return os.path.join('remote_repo_{0}'.format(repo.pk))


def get_apk_file_path(apk, filename):
    if hasattr(apk, 'repo'):
        return os.path.join(get_repo_path(apk.repo), filename)
    else:
        return os.path.join('packages', filename)


def get_graphic_asset_file_path(app_translation, filename):
    app = app_translation.master
    language_code = to_universal_language_code(app_translation.language_code)
    path = os.path.join(get_repo_path(app.repo), app.package_id, language_code)
    return os.path.join(path, filename)


def get_screenshot_file_path(screenshot, filename):
    path = os.path.join(get_repo_path(screenshot.app.repo), screenshot.get_relative_path())
    return os.path.join(path, filename)


def get_icon_file_path(repo, filename):
    if hasattr(repo, 'user'):
        icon_path = os.path.join('icons', filename)
        return os.path.join(get_repo_path(repo), icon_path)
    else:
        return os.path.join(get_remote_repo_path(repo), filename)


def get_icon_file_path_for_app(app, filename):
    if hasattr(app.repo, 'user'):
        icon_path = os.path.join('icons-640', filename)
        return os.path.join(get_repo_path(app.repo), icon_path)
    else:
        return os.path.join(get_remote_repo_path(app.repo), filename)


def get_identity_file_path(storage, filename):
    return os.path.join(get_repo_root_path(storage.repo), filename)


class RepoStorage(FileSystemStorage):

    def link(self, source, target):
        """
        Links or copies the source file to the target file.
        :param source: path to source file relative to self.location
        :param target: path to target file relative to self.location
        :return: The final relative path to the target file, can be different from :param target
        """
        target_dir = os.path.dirname(target)
        abs_source = os.path.join(self.location, source)
        abs_target = os.path.join(self.location, target)
        abs_target = self.get_available_name(abs_target)
        target_path = os.path.dirname(abs_target)

        if not os.path.exists(target_path):
            os.makedirs(target_path)
        # TODO support operating systems without support for os.link()
        os.link(abs_source, abs_target)

        rel_target = os.path.join(target_dir, os.path.basename(abs_target))
        return rel_target


class PrivateStorage(FileSystemStorage):

    def __init__(self, file_permissions_mode=0o600, directory_permissions_mode=0o700):
        super(PrivateStorage, self).__init__(settings.PRIVATE_REPO_ROOT, None,
                                             file_permissions_mode,
                                             directory_permissions_mode)
