from django.conf import settings
from django.forms import BooleanField
from django.utils.translation import ugettext_lazy as _

from maker.models import SshStorage
from .storage import StorageForm, MainStorageMixin, StorageCreateView, StorageDetailView, \
    StorageUpdateView, StorageDeleteView


class SshStorageForm(StorageForm):
    if settings.SINGLE_USER_MODE:
        ignore_identity_file = BooleanField(required=False, initial=True,
                                            label=_('Use local default SSH Key'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:  # don't show identity_file option when updating
            del self.fields['ignore_identity_file']

    def get_initial_for_field(self, field, field_name):
        if field_name == 'ignore_identity_file' and self.instance.pk:
            return not bool(self.instance.identity_file)  # True if no identity file exists
        return super().get_initial_for_field(field, field_name)

    class Meta(StorageForm.Meta):
        model = SshStorage
        fields = ['username', 'host', 'path', 'url']
        if settings.SINGLE_USER_MODE:
            fields += ['ignore_identity_file']
        labels = {
            'username': _('User Name'),
            'url': _('URL'),
        }
        help_texts = {
            'url': _('This is the location where the uploaded files can be accessed from.'),
        }


class SshKeyMixin(MainStorageMixin):

    def form_valid(self, form):
        if 'ignore_identity_file' in form.cleaned_data \
                and not form.cleaned_data['ignore_identity_file'] \
                and not form.instance.identity_file:
            result = super(SshKeyMixin, self).form_valid(form)  # validate rest of the form and save
            form.instance.create_identity_file()
            return result
        return super(SshKeyMixin, self).form_valid(form)


class SshStorageCreate(SshKeyMixin, StorageCreateView):
    model = SshStorage
    form_class = SshStorageForm


class SshStorageUpdate(SshKeyMixin, StorageUpdateView):
    model = SshStorage
    form_class = SshStorageForm


class SshStorageDetail(StorageDetailView):
    model = SshStorage
    template_name = 'maker/storage/detail_ssh.html'


class SshStorageDelete(StorageDeleteView):
    model = SshStorage
