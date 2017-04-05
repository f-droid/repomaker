import datetime
import logging
import os
from io import BytesIO

import requests
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from fdroidserver import common
from fdroidserver import update

from maker import tasks
from maker.storage import get_apk_file_path, RepoStorage
from .app import Repository, RemoteApp, App


class Apk(models.Model):
    package_id = models.CharField(max_length=255, blank=True)
    file = models.FileField(storage=RepoStorage())
    version_name = models.CharField(max_length=128, blank=True)
    version_code = models.PositiveIntegerField(default=0)
    size = models.PositiveIntegerField(default=0)
    signature = models.CharField(max_length=512, blank=True)
    hash = models.CharField(max_length=512, blank=True)
    hash_type = models.CharField(max_length=32, blank=True)
    added_date = models.DateTimeField(default=timezone.now)
    is_downloading = models.BooleanField(default=False)

    def __str__(self):
        return self.package_id + " " + str(self.version_code) + " " + self.file.name

    def download_async(self, url):
        """
        Downloads the APK file asynchronously if it is still missing.
        """
        if not self.file:
            tasks.download_apk(self.pk, url)

    def download(self, url):
        """
        Starts a blocking download of the APK file if it is still missing
        and then saves it.

        This also updates all pointers and links/copies the file to them.
        """
        if self.file:
            return

        # download and store file
        file_name = get_apk_file_path(self, url.rsplit('/', 1)[-1])
        r = requests.get(url)
        if r.status_code != requests.codes.ok:
            r.raise_for_status()
        self.file.save(file_name, BytesIO(r.content), save=True)

        # update apk pointers
        pointers = ApkPointer.objects.filter(apk=self).all()
        for pointer in pointers:
            pointer.link_file_from_apk()
            pointer.repo.update_async()

    @staticmethod
    def from_json(package_info):
        """
        Returns an Apk object created from index v1 JSON package information.

        Attention: This only returns the object, but does not save it.
        """
        apk = Apk(
            package_id=package_info['packageName'],
            version_name=package_info['versionName'],
            size=package_info['size'],
            hash=package_info['hash'],
            hash_type=package_info['hashType'],
            added_date=datetime.datetime.fromtimestamp(package_info['added'] / 1000,
                                                       timezone.utc)
        )
        if 'versionCode' in package_info:
            apk.version_code = package_info['versionCode']
        if 'sig' in package_info:
            apk.signature = package_info['sig']
        return apk

    def delete_if_no_pointers(self):
        # TODO delete Apk if there are no other pointers
        pass

    class Meta:
        unique_together = (("package_id", "hash"),)


class AbstractApkPointer(models.Model):
    apk = models.ForeignKey(Apk, on_delete=models.CASCADE, null=True)
    file = models.FileField(upload_to=get_apk_file_path, storage=RepoStorage())

    def __str__(self):
        return self.file.name

    class Meta:
        abstract = True


class ApkPointer(AbstractApkPointer):
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
    app = models.ForeignKey(App, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.app.__str__() + " - " + super().__str__()

    def initialize(self):
        """
        Initializes this object based on information retrieved from self.file.
        When done, this object will point to an App from self.repo
        and to a globally stored Apk.

        :return: Instance of HttpResponse in case of error, None otherwise
        """
        apk_info = self._get_info_from_file()
        if apk_info is None:
            raise ValidationError('Invalid APK.')
        self._attach_apk(apk_info)
        self._attach_app(apk_info)
        self.save()

    def _get_info_from_file(self):
        """
        Scans the APK file and returns a dictionary of information.
        It also extracts icons and stores them in the repository on disk.

        :return: A dict of APK information or None
        """
        self.repo.get_config()
        filename = os.path.basename(self.file.name)
        skip, apk_info, _ = update.scan_apk({}, filename, self.repo.get_repo_path(),
                                            common.KnownApks(), False)
        if skip:
            return None
        return apk_info

    def _attach_apk(self, apk_info):
        """
        Attaches either an existing or a new Apk to this object.

        :param apk_info: A dict with information about the APK as returned by get_info_from_file()
        """
        apk_set = Apk.objects.filter(package_id=apk_info['packageName'], hash=apk_info['hash'])
        if apk_set.exists():
            self.apk = apk_set.get()
        else:
            apk = Apk.objects.create(
                package_id=apk_info['packageName'],
                version_name=apk_info['versionName'],
                version_code=apk_info['versionCode'],
                size=apk_info['size'],
                signature=apk_info['sig'],
                hash=apk_info['hash'],
                hash_type=apk_info['hashType']
            )
            apk.save()
            self.apk = apk

        # hardlink/copy file if it does not exist, yet
        if not self.apk.file:
            source = self.file.name
            target = get_apk_file_path(None, os.path.basename(self.file.name))
            target = self.file.storage.link(source, target)
            self.apk.file.name = target
            self.apk.save()

    def _attach_app(self, apk_info):
        """
        Attaches either an existing or a new App to this object
        and updates app information if this Apk holds more recent information.

        :param apk_info: A dict with information about the APK as returned by get_info_from_file()
        """
        # check if app exists already in repo and if so, get latest version
        latest_version = self.apk.version_code
        try:
            old_app = App.objects.get(repo=self.repo, package_id=self.apk.package_id)
            existing_pointers = ApkPointer.objects.filter(app=old_app)
            for pointer in existing_pointers:
                if pointer.apk.version_code > latest_version:
                    latest_version = pointer.apk.version_code
                if pointer.apk.signature != self.apk.signature:
                    raise ValidationError(
                        'This app \'%s\' already exists in your repo, ' % self.apk.package_id
                        + 'but has a different signature.')
            self.app = old_app
        except ObjectDoesNotExist:
            app = App.objects.create(
                repo=self.repo,
                package_id=self.apk.package_id,
            )
            app.save()
            self.app = app

        # apply latest info to the app itself
        if self.apk.version_code == latest_version:
            self.app.name = apk_info['name']
            if 'icon' in apk_info and apk_info['icon'] is not None:
                icon_path = os.path.join(self.repo.get_repo_path(), "icons-640", apk_info['icon'])
                if os.path.isfile(icon_path):
                    self.app.delete_old_icon()
                    self.app.icon.save(apk_info['icon'], File(open(icon_path, 'rb')), save=False)
            self.app.save()

    def link_file_from_apk(self):
        """
        Hardlinks/copies the APK file from Apk if it does not exist, yet.

        This is the reverse of what happens in _attach_apk()
        """
        if self.file:
            return  # there's a file already, so nothing to do here

        # create the link/copy from source to target APK
        source = self.apk.file.name
        target = get_apk_file_path(self, os.path.basename(self.apk.file.name))
        target = self.apk.file.storage.link(source, target)

        # store the target filename in this pointer
        self.file.name = target
        self.save()

    class Meta(AbstractApkPointer.Meta):
        unique_together = (("apk", "app"),)


class RemoteApkPointer(AbstractApkPointer):
    app = models.ForeignKey(RemoteApp, on_delete=models.CASCADE)
    url = models.URLField(max_length=2048)

    def __str__(self):
        return self.app.__str__() + " - " + super().__str__()

    class Meta(AbstractApkPointer.Meta):
        unique_together = (("apk", "app"),)


@receiver(post_delete, sender=Apk)
def apk_post_delete_handler(**kwargs):
    apk = kwargs['instance']
    logging.info("Deleting APK: %s" % apk.file.name)
    apk.file.delete(save=False)


@receiver(post_delete, sender=ApkPointer)
def apk_pointer_post_delete_handler(**kwargs):
    apk = kwargs['instance']
    logging.info("Deleting APK Pointer: %s" % apk.file.name)
    apk.file.delete(save=False)
    apk.apk.delete_if_no_pointers()


@receiver(post_delete, sender=RemoteApkPointer)
def remote_apk_pointer_post_delete_handler(**kwargs):
    apk = kwargs['instance']
    logging.info("Deleting Remote APK Pointer: %s" % apk.file.name)
    apk.file.delete(save=False)
    apk.apk.delete_if_no_pointers()
