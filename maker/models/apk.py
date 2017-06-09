import logging
import os
import zipfile
from datetime import datetime
from io import BytesIO

import magic  # this is python-magic in requirements.txt
import requests
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from fdroidserver import common, exception, update
from fdroidserver.update import get_all_icon_dirs

from maker import tasks
from maker.models.repository import AbstractRepository
from maker.storage import get_apk_file_path, RepoStorage
from .app import Repository, RemoteApp, App, OTHER, IMAGE, VIDEO, AUDIO, DOCUMENT, BOOK, APK


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

        # TODO
        # update apk pointers
        pointers = ApkPointer.objects.filter(apk=apk).all()
        for pointer in pointers:
            pointer.link_file_from_apk()
            pointer.repo.update_async()

    def initialize(self, repo=None):
        """
        Initializes this object based on information retrieved from self.file.

        :param repo: If a Repository is passed here, an ApkPointer (and if needed an App)
                     are created as well.
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

        repo_file['hash'] = update.sha256sum(self.file.path)
        repo_file['hashType'] = 'sha256'
        repo_file['size'] = self.file.size

        apk_set = Apk.objects.filter(package_id=repo_file['packageName'], hash=repo_file['hash'])
        if not apk_set.exists():
            self.apply_json_package_info(repo_file)
            self.save()
            apk = self
        elif apk_set.count() == 1:
            self.delete()
            apk = apk_set[0]
        else:
            raise RuntimeError('More than one APK with package ID %s' % repo_file['packageName'])

        if repo is not None:
            pointer = ApkPointer(apk=apk, repo=repo)
            pointer.initialize(repo_file)

        return apk

    def _get_info_from_apk(self):
        """
        Scans the APK file and returns a dictionary of information.
        It also extracts icons and stores them in the repository on disk.

        :return: A dict of APK information or None
        """
        AbstractRepository().get_config()

        # verify APK before scanning
        if not common.verify_apk_signature(self.file.path):
            raise ValidationError(_('Invalid APK signature.'))

        # scan APK and extract information about it
        repo_file = {'type': APK, 'icons_src': {}, 'uses-permission': []}
        try:
            # TODO switch to androguard when available
            update.scan_apk_aapt(repo_file, self.file.path)
        except exception.BuildException as e:
            raise ValidationError(e)

        if 'packageName' not in repo_file:
            raise ValidationError(_('Invalid APK.'))

        repo_file['sig'] = update.getsig(self.file.path)
        if not repo_file['sig']:
            raise ValidationError(_('Failed to retrieve APK signature.'))

        return repo_file

    def _get_info_from_file(self):
        repo_file = {
            'sig': None,
            'hash': update.sha256sum(self.file.path),
            'hashType': 'sha256',
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
        mime = magic.from_file(self.file.path, mime=True)
        mime_start = mime.split('/', 1)[0]
        ext = os.path.splitext(self.file.name)[1]
        if mime_start == 'image':
            return IMAGE
        if mime_start == 'video':
            return VIDEO
        if mime_start == 'audio':
            return AUDIO
        if mime == 'application/epub+zip' or ext == '.mobi':
            return BOOK
        if mime == 'application/pdf' or mime.startswith('application/vnd.oasis.opendocument') \
                or ext == '.docx' or ext == '.txt':
            return DOCUMENT
        # TODO add more types
        if ext.startswith('.php') or ext == '.py' or ext == '.pl' or ext == '.cgi':
            raise ValidationError(_('Unsupported File Type'))
        return OTHER

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


class AbstractApkPointer(models.Model):
    apk = models.ForeignKey(Apk, on_delete=models.CASCADE, null=True)

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
            app.save()
            self.app = app
        elif apps.count() == 1:
            old_app = apps[0]
            if old_app.type != apk_info['type']:
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


@receiver(post_delete, sender=Apk)
def apk_post_delete_handler(**kwargs):
    apk = kwargs['instance']
    logging.info("Deleting APK: %s", apk.file.name)
    apk.file.delete(save=False)


@receiver(post_delete, sender=ApkPointer)
def apk_pointer_post_delete_handler(**kwargs):
    apk_pointer = kwargs['instance']
    logging.info("Deleting APK Pointer: %s", apk_pointer.file.name)
    apk_pointer.file.delete(save=False)
    if apk_pointer.apk:
        apk_pointer.delete_app_icons_from_repo()
        apk_pointer.apk.delete_if_no_pointers()


@receiver(post_delete, sender=RemoteApkPointer)
def remote_apk_pointer_post_delete_handler(**kwargs):
    remote_apk_pointer = kwargs['instance']
    logging.info("Deleting Remote APK Pointer: %s", remote_apk_pointer)
    remote_apk_pointer.apk.delete_if_no_pointers()
