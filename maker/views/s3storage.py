from django.forms import PasswordInput
from django.utils.translation import ugettext_lazy as _

from maker.models import S3Storage
from . import BaseModelForm
from .storage import StorageCreateView, StorageUpdateView, StorageDeleteView


class S3StorageForm(BaseModelForm):
    class Meta:
        model = S3Storage
        fields = ['region', 'bucket', 'accesskeyid', 'secretkey']
        labels = {
            'bucket': _('Bucket Name'),
            'accesskeyid': _('Access Key ID'),
            'secretkey': _('Secret Access Key'),
        }
        help_texts = {
            'region': _('Other regions are currently not supported.'),
        }
        widgets = {
            'secretkey': PasswordInput(),
        }


class S3StorageCreate(StorageCreateView):
    model = S3Storage
    form_class = S3StorageForm


class S3StorageUpdate(StorageUpdateView):
    model = S3Storage
    form_class = S3StorageForm


class S3StorageDelete(StorageDeleteView):
    model = S3Storage
