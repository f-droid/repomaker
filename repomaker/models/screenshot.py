import logging
import os
from io import BytesIO

import requests
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import ugettext_lazy as _

from repomaker import tasks
from repomaker.storage import get_screenshot_file_path, RepoStorage
from repomaker.utils import to_universal_language_code
from .app import App
from .remoteapp import RemoteApp

PHONE = 'phoneScreenshots'
SEVEN_INCH = 'sevenInchScreenshots'
TEN_INCH = 'tenInchScreenshots'
TV = 'tvScreenshots'
WEAR = 'wearScreenshots'
TYPE_CHOICES = (
    (PHONE, _('Phone')),
    (SEVEN_INCH, _("7'' Tablet")),
    (TEN_INCH, _("10'' Tablet")),
    (TV, _('TV')),
    (WEAR, _('Wearable')),
)


class AbstractScreenshot(models.Model):
    language_code = models.CharField(max_length=32, default='en')
    type = models.CharField(max_length=32, choices=TYPE_CHOICES, default=PHONE)

    def __str__(self):
        return self.app.__str__() + " - " + self.language_code + " " + self.type

    def get_url(self):
        raise NotImplementedError()

    class Meta:
        abstract = True


class Screenshot(AbstractScreenshot):
    app = models.ForeignKey(App, on_delete=models.CASCADE)
    file = models.ImageField(upload_to=get_screenshot_file_path, storage=RepoStorage(),
                             max_length=1024)
    # TODO add a thumbnail to be automatically generated from file

    def __str__(self):
        return super(Screenshot, self).__str__() + " " + self.file.name

    def get_relative_path(self):
        language_code = to_universal_language_code(self.language_code)
        return os.path.join(self.app.package_id, language_code, self.type)

    def get_url(self):
        return self.file.url


class RemoteScreenshot(AbstractScreenshot):
    app = models.ForeignKey(RemoteApp, on_delete=models.CASCADE)
    url = models.URLField(max_length=2048)

    def __str__(self):
        return super(RemoteScreenshot, self).__str__() + " " + os.path.basename(self.url)

    def get_url(self):
        return self.url

    @staticmethod
    def add(language_code, s_type, app, base_url, files):
        """
        Creates and saves one or more new RemoteScreenshots if the given s_type is supported.
        """
        if not is_supported_type(s_type):
            return
        for file in files:
            url = base_url + file
            if not RemoteScreenshot.objects.filter(language_code=language_code, type=s_type,
                                                   app=app, url=url).exists():
                screenshot = RemoteScreenshot(language_code=language_code, type=s_type, app=app,
                                              url=url)
                screenshot.save()

    def download_async(self, app):
        """
        Downloads this RemoteScreenshot asynchronously and creates a local Screenshot if successful.
        """
        tasks.download_remote_screenshot(self.pk, app.pk)

    def download(self, app_id):
        """
        Does a blocking download of this RemoteScreenshot
        and creates a local Screenshot if successful.
        """
        screenshot = Screenshot(language_code=self.language_code, type=self.type, app_id=app_id)
        r = requests.get(self.url)
        if r.status_code == requests.codes.ok:
            screenshot.file.save(os.path.basename(self.url), BytesIO(r.content), save=True)


def is_supported_type(s_type):
    for t in TYPE_CHOICES:
        if s_type == t[0]:
            return True
    return False


@receiver(post_delete, sender=Screenshot)
def screenshot_post_delete_handler(**kwargs):
    apk = kwargs['instance']
    logging.info("Deleting Screenshot: %s", apk.file.name)
    apk.file.delete(save=False)
