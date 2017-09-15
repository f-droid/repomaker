import fdroidserver.index
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.forms import CharField, URLField, TextInput
from django.utils.translation import ugettext_lazy as _
from repomaker.models.storage import GitStorage, HostnameValidator, PathValidator

from .sshstorage import SshStorageForm, SshKeyMixin
from .storage import StorageCreateView, StorageUpdateView, StorageDeleteView, StorageDetailView


class GitStorageForm(SshStorageForm):
    ssh_url = CharField(required=True, label=_('SSH'),
                        widget=TextInput(attrs={'placeholder': _('Enter SSH URL')}))
    url = URLField(required=False, label=_('Raw Git URL'), help_text=_(
        'This is the location where the uploaded files can be accessed from' +
        ' in raw form.' +
        ' Leave empty for GitHub or GitLab.com repositories.'))

    def get_initial_for_field(self, field, field_name):
        if field_name == 'ssh_url' and self.instance.pk:
            return self.instance.get_remote_url()
        return super(GitStorageForm, self).get_initial_for_field(field, field_name)

    class Meta(SshStorageForm.Meta):
        model = GitStorage
        fields = ['ssh_url', 'url']


class GitUrlValidationMixin(SshKeyMixin):

    def form_valid(self, form):
        # check that ssh_url starts with git@
        if not form.cleaned_data['ssh_url'].startswith('git@'):
            form.add_error('ssh_url', _("This URL must start with 'git@'."))
            return self.form_invalid(form)

        # strip the standard git user name from the URL
        ssh_url = form.cleaned_data['ssh_url'].replace('git@', '')

        # check that ssh_url ends with .git
        if not ssh_url.endswith('.git'):
            form.add_error('ssh_url', _("This URL must end with '.git'."))
            return self.form_invalid(form)

        # strip the .git ending from the URL
        ssh_url = ssh_url.replace('.git', '')

        # check that ssh_url includes a path
        url_error = _("This URL is invalid. Please copy the exact SSH URL of your git repository.")
        if ':' not in ssh_url:
            form.add_error('ssh_url', url_error)
            return self.form_invalid(form)

        # extract hostname and path from URL
        (hostname, path) = ssh_url.split(':', 1)

        # validate hostname and path
        try:
            HostnameValidator().__call__(hostname)
            PathValidator().__call__('/' + path)
        except ValidationError:
            form.add_error('ssh_url', url_error)
            return self.form_invalid(form)

        # assign hostname and path to the GitStorage object
        form.instance.host = hostname
        form.instance.path = path

        # try to generate the F-Droid repo URL from the git repo URL
        mirror_urls = fdroidserver.index.get_mirror_service_urls(form.cleaned_data['ssh_url'])
        if len(mirror_urls) > 0:
            form.instance.url = mirror_urls[0]
        # URL generation failed, so the user needs to provide a valid URL
        else:
            try:
                URLValidator().__call__(form.cleaned_data['ssh_url'])
            except ValidationError:
                form.add_error('url', _('Please add a valid URL' +
                                        'for the raw content of this git repository.'))
                return self.form_invalid(form)

        return super(GitUrlValidationMixin, self).form_valid(form)


class GitStorageCreate(GitUrlValidationMixin, StorageCreateView):
    model = GitStorage
    form_class = GitStorageForm
    template_name = 'repomaker/storage/form_git.html'


class GitStorageUpdate(GitUrlValidationMixin, StorageUpdateView):
    model = GitStorage
    form_class = GitStorageForm


class GitStorageDetail(StorageDetailView):
    model = GitStorage
    template_name = 'repomaker/storage/detail_git.html'


class GitStorageDelete(StorageDeleteView):
    model = GitStorage
