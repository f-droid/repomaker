from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm, BooleanField
from django.utils.decorators import method_decorator

from maker.models import SshStorage
from .storage import StorageCreateView, StorageUpdateView, StorageDeleteView


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


@method_decorator(login_required, name='dispatch')
class SshStorageCreate(StorageCreateView):
    model = SshStorage
    form_class = SshStorageForm


@method_decorator(login_required, name='dispatch')
class SshStorageUpdate(StorageUpdateView):
    model = SshStorage
    form_class = SshStorageForm


@method_decorator(login_required, name='dispatch')
class SshStorageDelete(StorageDeleteView):
    model = SshStorage
