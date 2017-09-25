import logging
import os
import zipfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _
from fdroidserver import update
from fdroidserver.update import get_all_icon_dirs
from repomaker.storage import get_apk_file_path, RepoStorage

from .app import App
from .remoteapp import RemoteApp
from .repository import Repository


class AbstractApkPointer(models.Model):
    apk = models.ForeignKey('Apk', on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.app.__str__() + " - " + str(self.apk.version_code)

    class Meta:
        abstract = True


class ApkPointer(AbstractApkPointer):
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
    app = models.ForeignKey(App, on_delete=models.CASCADE, null=True)
    file = models.FileField(upload_to=get_apk_file_path, storage=RepoStorage())

    def __str__(self):
        return super().__str__() + " - " + self.file.name

    def initialize(self, apk_info):
        """
        Attaches either an existing or a new App to this object
        and updates app information if this Apk holds more recent information.

        :param apk_info: A dict with information about the APK as returned by get_info_from_file()
        """
        if not self.apk or not self.apk.package_id or not self.repo:
            raise RuntimeError('Trying to initialize incomplete ApkPointer.')

        # Link/Copy file from Apk to this pointer
        self.link_file_from_apk()

        # check if app exists already in repo and if so, get latest version
        latest_version = self.apk.version_code
        apps = App.objects.filter(repo=self.repo, package_id=self.apk.package_id)
        if not apps.exists():
            app = App.objects.create(
                repo=self.repo,
                package_id=self.apk.package_id,
                type=apk_info['type'],
            )
            app.default_translate()
            app.save()
            self.app = app
        elif apps.count() == 1:
            old_app = apps[0]
            if old_app.type != apk_info['type']:
                # TODO clarify filename and app in the error message
                raise ValidationError(
                    _('This file is of a different type than the other versions of this app.'))
            existing_pointers = ApkPointer.objects.filter(app=old_app)
            for pointer in existing_pointers:
                if pointer.apk.version_code > latest_version:
                    latest_version = pointer.apk.version_code
                if pointer.apk.signature != self.apk.signature:
                    raise ValidationError(
                        'This app \'%s\' already exists in your repo, ' % self.apk.package_id +
                        'but has a different signature.')
            self.app = old_app
        else:
            raise RuntimeError('More than one app in repo %d with package ID %s' %
                               (self.repo.pk, self.apk.package_id))

        # apply latest info to the app itself
        if self.apk.version_code == latest_version:
            # update app name
            self.app.name = apk_info['name']
            if not self.app.name:  # if the app has no name, use the package name instead
                self.app.name = self.app.package_id

            # update app icon
            if 'icons_src' in apk_info and '-1' in apk_info['icons_src']:
                icon_src = apk_info['icons_src']['-1']
                if '640' in apk_info['icons_src']:
                    # try higher resolution and use if available
                    icon_src = apk_info['icons_src']['640']
                # this will be overwritten on the next repo update
                with zipfile.ZipFile(self.file.path, 'r') as f:
                    self.app.delete_old_icon()
                    icon_name = "%s.%s.png" % (apk_info['packageName'], apk_info['versionCode'])
                    icon_bytes = update.get_icon_bytes(f, icon_src)
                    self.app.icon.save(icon_name, BytesIO(icon_bytes), save=False)
            self.app.save()
        self.save()

    def link_file_from_apk(self):
        """
        Hardlinks/copies the APK file from Apk if it does not exist, yet.

        This is the reverse of what happens in _attach_apk()
        """
        if self.file:
            return  # there's a file already, so nothing to do here

        # create the link/copy from source to target APK
        source = self.apk.file.name
        if not self.apk.file:
            raise RuntimeError('Trying to link to a non-existing APK.')
        target = get_apk_file_path(self, os.path.basename(self.apk.file.name))
        target = self.apk.file.storage.link(source, target)

        # store the target filename in this pointer
        self.file.name = target
        self.save()

    def delete_app_icons_from_repo(self):
        # Build icon name
        icon_name = self.apk.package_id + "." + str(self.apk.version_code) + ".png"

        # Get path of repository
        path = self.repo.get_repo_path()

        # List with icon directories
        icon_directories = get_all_icon_dirs(path)
        for icon_directory in icon_directories:
            icon = os.path.join(icon_directory, icon_name)
            try:
                if self.app and self.app.icon and icon == self.app.icon.path:
                    continue  # do not delete current app icon
            except App.DoesNotExist:
                pass  # if the app already was deleted, we need to remove the icons
            if os.path.isfile(icon):
                os.remove(icon)

    class Meta(AbstractApkPointer.Meta):
        unique_together = (("apk", "app"),)


class RemoteApkPointer(AbstractApkPointer):
    app = models.ForeignKey(RemoteApp, on_delete=models.CASCADE)
    url = models.URLField(max_length=2048)

    def __str__(self):
        return super().__str__() + " - " + os.path.basename(self.url)

    class Meta(AbstractApkPointer.Meta):
        unique_together = (("apk", "app"),)


@receiver(post_delete, sender=ApkPointer)
def apk_pointer_post_delete_handler(**kwargs):
    from repomaker.models import Apk
    apk_pointer = kwargs['instance']
    logging.info("Deleting APK Pointer: %s", apk_pointer.file.name)
    apk_pointer.file.delete(save=False)
    try:
        if apk_pointer.apk:
            apk_pointer.delete_app_icons_from_repo()
            apk_pointer.apk.delete_if_no_pointers()
    except Apk.DoesNotExist:
        pass  # APK must have been deleted already


@receiver(post_delete, sender=RemoteApkPointer)
def remote_apk_pointer_post_delete_handler(**kwargs):
    from repomaker.models import Apk
    remote_apk_pointer = kwargs['instance']
    logging.info("Deleting Remote APK Pointer: %s", remote_apk_pointer)
    try:
        remote_apk_pointer.apk.delete_if_no_pointers()
    except Apk.DoesNotExist:
        pass  # APK must have been deleted already
