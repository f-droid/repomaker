from django.conf import settings
from django.forms import BooleanField

from maker.models import SshStorage
from . import BaseModelForm
from .storage import StorageCreateView, StorageUpdateView, StorageDeleteView


class SshStorageForm(BaseModelForm):
    if settings.SINGLE_USER_MODE:
        ignore_identity_file = BooleanField(required=False, initial=True, disabled=True,
                                            label='Use local default SSH Key')

    class Meta:
        model = SshStorage
        fields = ['username', 'host', 'path', 'url']
        if settings.SINGLE_USER_MODE:
            fields += ['ignore_identity_file']
        labels = {
            'username': 'User Name',
            'url': 'URL',
        }
        help_texts = {
            'url': 'This is the location where the uploaded files can be accessed from.',
        }


class SshStorageCreate(StorageCreateView):
    model = SshStorage
    form_class = SshStorageForm


class SshStorageUpdate(StorageUpdateView):
    model = SshStorage
    form_class = SshStorageForm


class SshStorageDelete(StorageDeleteView):
    model = SshStorage
