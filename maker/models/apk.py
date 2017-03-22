import logging
import os

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.forms import ModelForm
from django.http import HttpResponseServerError
from django.utils import timezone
from fdroidserver import common
from fdroidserver import update

from maker.storage import get_apk_file_path, RepoStorage
from .app import App


class Apk(models.Model):
    app = models.ForeignKey(App, on_delete=models.CASCADE)
    file = models.FileField(upload_to=get_apk_file_path, storage=RepoStorage())
    version_name = models.CharField(max_length=128, blank=True)
    version_code = models.PositiveIntegerField(default=0)
    size = models.PositiveIntegerField(default=0)
    signature = models.CharField(max_length=512, blank=True)
    hash = models.CharField(max_length=512, blank=True)
    hash_type = models.CharField(max_length=32, blank=True)
    added_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.file.name

    def store_data_from_file(self):
        """
        Scans self.file and stores the retrieved data
        :return: Instance of HttpResponse in case of error, None otherwise
        """
        repo = self.app.repo
        repo.get_config()
        filename = os.path.basename(self.file.name)
        skip, apk_info, _ = update.scan_apk({}, filename, repo.get_repo_path(), common.KnownApks(),
                                            False)
        if skip:
            return HttpResponseServerError('Invalid APK.')

        # apply scanned info from APK
        self.version_name = apk_info['versionName']
        self.version_code = apk_info['versionCode']
        self.size = apk_info['size']
        self.signature = apk_info['sig']
        self.hash = apk_info['hash']
        self.hash_type = apk_info['hashType']

        # check if app exists already and if so, get latest version
        latest_version = self.version_code
        try:
            old_app = App.objects.get(repo=repo, package_id=apk_info['packageName'])
            existing_apks = Apk.objects.filter(app=old_app)
            for existing_apk in existing_apks:
                if existing_apk.version_code > latest_version:
                    latest_version = existing_apk.version_code
                if existing_apk.signature != self.signature:
                    return HttpResponseServerError(
                        'This app \'%s\' already exists in your repo,' % apk_info['packageName']
                        + 'but has a different signature.')
            app = self.app  # keep a copy of the temporary app
            self.app = old_app
            self.save()  # to prevent it from getting deleted when deleting temporary app next
            app.delete()
        except ObjectDoesNotExist:
            self.app.package_id = apk_info['packageName']

        # apply latest info to the app itself
        if self.version_code == latest_version:
            self.app.name = apk_info['name']
            if 'icon' in apk_info and apk_info['icon'] is not None:
                icon_path = os.path.join(repo.get_repo_path(), "icons", apk_info['icon'])
                if os.path.isfile(icon_path):
                    self.app.icon.save(apk_info['icon'], File(open(icon_path, 'rb')))

        # save APK and app
        self.save()
        self.app.save()
        return None

    class Meta:
        unique_together = (("app", "version_code"), ("app", "hash"))


@receiver(post_delete, sender=Apk)
def apk_post_delete_handler(**kwargs):
    apk = kwargs['instance']
    if apk.file is not None and apk.file != settings.REPO_DEFAULT_ICON:
        logging.info("Deleting APK: %s" % apk.file.name)
        apk.file.delete(False)


class ApkForm(ModelForm):
    class Meta:
        model = Apk
        fields = ['file']
