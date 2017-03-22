import logging

from django.db import models
from fdroidserver import server
from libcloud.storage.types import Provider

from maker.storage import REPO_DIR
from .repository import Repository


class S3Storage(models.Model):
    repo = models.ForeignKey(Repository, on_delete=models.CASCADE)
    REGION_CHOICES = (
        (Provider.S3, 'US Standard'),
    )
    region = models.CharField(max_length=32, choices=REGION_CHOICES, default=Provider.S3)
    bucket = models.CharField(max_length=128)
    accesskeyid = models.CharField(max_length=128)
    secretkey = models.CharField(max_length=255)

    def __str__(self):
        return 's3://' + str(self.bucket)

    def get_url(self):
        # This needs to be changed when more region choices are added
        return "https://s3.amazonaws.com/" + str(self.bucket)

    def get_repo_url(self):
        return self.get_url() + "/fdroid/" + REPO_DIR

    def publish(self):
        logging.info("Publishing '%s' to %s" % (self.repo, self))
        config = self.repo.get_config()
        config['awsbucket'] = self.bucket
        config['awsaccesskeyid'] = self.accesskeyid
        config['awssecretkey'] = self.secretkey
        server.update_awsbucket(REPO_DIR)
