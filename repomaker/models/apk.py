import logging
import os
import zipfile
from datetime import datetime
from io import BytesIO

import magic  # this is python-magic in requirements.txt
import requests
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from fdroidserver import common, exception, update

from repomaker import tasks
from repomaker.models.repository import AbstractRepository
from repomaker.storage import get_apk_file_path, RepoStorage
from .apkpointer import ApkPointer, RemoteApkPointer
from .app import IMAGE, VIDEO, AUDIO, DOCUMENT, BOOK, APK


class Apk(models.Model):
    package_id = models.CharField(max_length=255, blank=True)
    file = models.FileField(upload_to=get_apk_file_path, storage=RepoStorage())
    version_name = models.CharField(max_length=128, blank=True)
    version_code = models.PositiveIntegerField(default=0)
    size = models.PositiveIntegerField(default=0)
    signature = models.CharField(max_length=512, blank=True, null=True)
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
        file_name = url.rsplit('/', 1)[-1]
        r = requests.get(url)
        if r.status_code != requests.codes.ok:
            # TODO delete self and ApkPointer when this fails permanently
            r.raise_for_status()
        self.file.save(file_name, BytesIO(r.content), save=True)

        # initialize the APK and delete it if there was a problem
        try:
            apk = self.initialize()
        except ValidationError as e:
            logging.warning('Deleting invalid APK file: %s', e)
            ApkPointer.objects.filter(apk=self).all().delete()
            RemoteApkPointer.objects.filter(apk=self).all().delete()
            self.delete()
            return

        # update apk pointers
        pointers = ApkPointer.objects.filter(apk=apk).all()
        for pointer in pointers:
            pointer.link_file_from_apk()
            pointer.repo.update_async()

    def initialize(self, repo=None, app=None):
        """
        Initializes this object based on information retrieved from self.file.

        :param repo: If a Repository is passed here, an ApkPointer (and if needed an App)
                     are created as well.
        :param app: If an App is passed here, the Apk needs to be an update for this app,
                    otherwise a ValidationError will be raised.
        :raises: ValidationError if Apk can not be initialized. Delete it, if you get this error!
        :return: An instance of this Apk objects or a different one if it existed already
        """
        if not self.file:
            raise RuntimeError('Trying to initialize an Apk without file')

        ext = os.path.splitext(self.file.name)[1]
        if ext == '.apk':
            try:
                repo_file = self._get_info_from_apk()
            except exception.BuildException as e:
                raise ValidationError(e)
            except zipfile.BadZipFile as e:
                raise ValidationError(e)
        else:
            repo_file = self._get_info_from_file()

        if app is not None and app.package_id != repo_file['packageName']:
            raise ValidationError(_('This file is not an update for %s') % app.package_id)

        apk_set = Apk.objects.filter(package_id=repo_file['packageName'], hash=repo_file['hash'])
        if not apk_set.exists():
            self.apply_json_package_info(repo_file)
            self.save()
            apk = self
        elif apk_set.count() == 1 and self == apk_set[0]:
            # we are initializing a new APK from a remote repo,
            # so don't override APK info with local scanning data
            apk = self
        elif apk_set.count() == 1:
            logging.info("Existing Apk found, trying to reuse...")
            apk = apk_set[0]
            if not apk.file:
                apk.file = self.file
                apk.save()
                self.file = None
            self.delete()
        else:
            raise RuntimeError('More than one APK with package ID %s' % repo_file['packageName'])

        if repo is not None:
            if ApkPointer.objects.filter(apk=apk, repo=repo).exists():
                raise ValidationError(_('This APK already exists in the current repo.'))
            pointer = ApkPointer(apk=apk, repo=repo)
            pointer.initialize(repo_file)  # also saves the pointer

        return apk

    def _get_info_from_apk(self):
        """
        Scans the APK file and returns a dictionary of information.
        It also extracts icons and stores them in the repository on disk.

        :return: A dict of APK information or None
        """
        AbstractRepository().get_config()

        # Verify that the signature is correct
        if not common.verify_apk_signature(self.file.path):
            raise ValidationError(_('Invalid APK signature'))

        # scan APK and extract information about it
        try:
            repo_file = update.scan_apk(self.file.path)
            repo_file['type'] = APK
        except exception.BuildException as e:
            raise ValidationError(e)

        if 'packageName' not in repo_file:
            raise ValidationError(_('Invalid APK.'))

        return repo_file

    def _get_info_from_file(self):
        repo_file = {
            'sig': None,
            'hash': update.sha256sum(self.file.path),
            'hashType': 'sha256',
            'size': self.file.size,
            'type': self._get_type()
        }
        file_name = os.path.basename(self.file.name)
        match = common.STANDARD_FILE_NAME_REGEX.match(file_name)
        if match:
            repo_file['packageName'] = match.group(1)
            repo_file['versionName'] = match.group(2)
            repo_file['versionCode'] = int(match.group(2))
        else:
            repo_file['packageName'] = os.path.splitext(file_name)[0]
            repo_file['versionName'] = datetime.now().strftime('%Y-%m-%d')
            repo_file['versionCode'] = int(datetime.now().timestamp())
        repo_file['name'] = repo_file['packageName']

        return repo_file

    def _get_type(self):
        """
        Retrieves the file's type as str with mime-type checking if known to not be an APK.
        If you need extra file-types, please make sure to add them safely(!) here.
        :raises: ValidationError if doesn't match type on white-list.
        """
        ext = os.path.splitext(self.file.name)[1]
        # exclude dangerous extensions right from the beginning
        if ext.startswith('.php') or ext.startswith('.py') or ext == '.pl' or ext == '.cgi' or \
                ext == '.js' or ext == '.html':
            raise ValidationError(_('Unsupported File Type'))
        # allow a white-list of mime-types
        mime = magic.from_file(self.file.path, mime=True)
        mime_start = mime.split('/', 1)[0]
        if mime_start == 'image':
            return IMAGE
        if mime_start == 'video':
            return VIDEO
        if mime_start == 'audio':
            return AUDIO
        if mime == 'application/epub+zip':
            return BOOK
        if mime == 'application/pdf' or mime.startswith('application/vnd.oasis.opendocument') \
                or ext == '.docx' or ext == '.txt':
            return DOCUMENT
        raise ValidationError(_('Unsupported File Type'))

    def apply_json_package_info(self, package_info):
        """
        Saves package information from index v1 JSON to a fresh Apk object.

        Attention: This does not save the object.
        """
        if self.package_id:
            raise RuntimeError('Trying to apply information to an initialized Apk object.')
        self.package_id = package_info['packageName']
        self.version_name = package_info['versionName']
        self.size = package_info['size']
        self.hash = package_info['hash']
        self.hash_type = package_info['hashType']
        if 'added' in package_info:
            self.added_date = datetime.fromtimestamp(package_info['added'] / 1000, timezone.utc)
        if 'versionCode' in package_info:
            self.version_code = package_info['versionCode']
        if 'sig' in package_info:
            self.signature = package_info['sig']

    def delete_if_no_pointers(self):
        apk_pointers_exist = ApkPointer.objects.filter(apk=self).exists()
        remote_apk_pointers_exist = RemoteApkPointer.objects.filter(apk=self).exists()
        if not apk_pointers_exist and not remote_apk_pointers_exist:
            self.delete()


@receiver(pre_delete, sender=Apk)
def apk_pre_delete_handler(**kwargs):
    apk = kwargs['instance']
    # delete pointers first, so they can still access APK information when cleaning up
    ApkPointer.objects.filter(apk=apk).delete()
    RemoteApkPointer.objects.filter(apk=apk).delete()


@receiver(post_delete, sender=Apk)
def apk_post_delete_handler(**kwargs):
    apk = kwargs['instance']
    if apk.file:
        logging.info("Deleting APK: %s", apk.file.name)
        apk.file.delete(save=False)
