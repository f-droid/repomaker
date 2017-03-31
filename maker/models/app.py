import datetime
import os
from io import BytesIO

import requests
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from fdroidserver import metadata

from maker.storage import get_media_file_path_for_app
from .category import Category
from .repository import Repository, RemoteRepository


class AbstractApp(models.Model):
    package_id = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(max_length=2048, blank=True)
    icon = models.ImageField(upload_to=get_media_file_path_for_app,
                             default=settings.APP_DEFAULT_ICON)
    category = models.ManyToManyField(Category, blank=True, limit_choices_to={'user': None})
    added_date = models.DateTimeField(default=timezone.now)
    last_updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def to_metadata_app(self):
        meta = metadata.App()
        meta.id = self.package_id
        meta.WebSite = self.website
        meta.Summary = self.summary
        meta.Description = self.description
        meta.added = timezone.make_naive(self.added_date)
        meta.Categories = [category.name for category in self.category.all()]
        return meta

    def delete_old_icon(self):
        icon_path = os.path.dirname(self.icon.path)
        if icon_path != settings.MEDIA_ROOT:
            self.icon.delete(save=False)

    class Meta:
        abstract = True
        unique_together = (("package_id", "repo"),)


class App(AbstractApp):
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)

    def get_absolute_url(self):
        return reverse('app', kwargs={'repo_id': self.repo.pk, 'app_id': self.pk})


class RemoteApp(AbstractApp):
    repo = models.ForeignKey(RemoteRepository, on_delete=models.CASCADE)
    icon_etag = models.CharField(max_length=128, blank=True)

    def update_from_json(self, app):
        self.name = app['name']
        self.summary = app['summary']
        self.description = app['description']
        self.website = app['webSite']
        self._update_icon(app['icon'])
        self._update_categories(app['categories'])
        date_added = datetime.datetime.fromtimestamp(app['added'] / 1000, timezone.utc)
        if self.added_date > date_added:
            self.added_date = date_added
        self.save()

    def _update_icon(self, icon_name):
        url = self.repo.url + '/icons-640/' + icon_name
        headers = {}
        if self.icon_etag is not None and self.icon_etag != '':
            headers['If-None-Match'] = self.icon_etag
        r = requests.get(url, headers=headers)
        if r.status_code == requests.codes.ok:
            self.delete_old_icon()
            self.icon.save(icon_name, BytesIO(r.content), save=False)
            self.icon_etag = r.headers['ETag']

    def _update_categories(self, categories):
        if not self.pk:
            # we need to save before we can use a ManyToManyField
            self.save()
        for category in categories:
            try:
                cat = Category.objects.get(name=category)
                self.category.add(cat)
            except ObjectDoesNotExist:
                # Drop the unknown category, don't create new categories automatically here
                pass


@receiver(post_delete, sender=App)
def app_post_delete_handler(**kwargs):
    app = kwargs['instance']
    app.delete_old_icon()


@receiver(post_delete, sender=RemoteApp)
def app_post_delete_handler(**kwargs):
    app = kwargs['instance']
    app.delete_old_icon()
