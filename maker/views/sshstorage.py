from django.conf import settings
from django.forms import ModelForm, BooleanField

from maker.models import SshStorage
from .storage import StorageCreateView, StorageUpdateView, StorageDeleteView

NAME = "SSH Storage"


class SshStorageForm(ModelForm):
    if settings.SINGLE_USER_MODE:
        ignore_identity_file = BooleanField(required=False, initial=True, disabled=True,
                                            label='Use local default SSH Key')

    class Meta:
        model = SshStorage
        fields = ['username', 'host', 'path']
        if settings.SINGLE_USER_MODE:
            fields += ['ignore_identity_file']
        labels = {
            'username': 'User Name',
        }


class SshStorageCreate(StorageCreateView):
    model = SshStorage
    form_class = SshStorageForm

    def get_storage_name(self):
        return NAME


class SshStorageUpdate(StorageUpdateView):
    model = SshStorage
    form_class = SshStorageForm

    def get_storage_name(self):
        return NAME


class SshStorageDelete(StorageDeleteView):
    model = SshStorage
