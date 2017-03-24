import logging

from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from fdroidserver import metadata

from maker.storage import get_media_file_path_for_app
from .category import Category
from .repository import Repository


class App(models.Model):
    package_id = models.CharField(max_length=255, blank=True)
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, blank=True)
    summary = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(max_length=2048, blank=True)
    icon = models.ImageField(upload_to=get_media_file_path_for_app,
                             default=settings.REPO_DEFAULT_ICON)
    category = models.ManyToManyField(Category, blank=True, limit_choices_to={'user': None})
    added_date = models.DateTimeField(default=timezone.now)
    last_updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('app', kwargs={'repo_id': self.repo.pk, 'app_id': self.pk})

    def to_metadata_app(self):
        meta = metadata.App()
        meta.id = self.package_id
        meta.WebSite = self.website
        meta.Summary = self.summary
        meta.Description = self.description
        meta.added = timezone.make_naive(self.added_date)
        meta.Categories = [category.name for category in self.category.all()]
        return meta

    class Meta:
        unique_together = (("package_id", "repo"),)


@receiver(post_delete, sender=App)
def app_post_delete_handler(**kwargs):
    app = kwargs['instance']
    if app.icon is not None and app.icon != settings.REPO_DEFAULT_ICON:
        logging.info("Deleting app icon: %s" % app.icon.name)
        app.icon.delete(False)
