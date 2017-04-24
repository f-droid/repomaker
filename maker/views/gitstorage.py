import fdroidserver.index
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.forms import CharField, URLField
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DetailView

from maker.models.storage import GitStorage, HostnameValidator, PathValidator
from .sshstorage import SshStorageForm, SshKeyMixin
from .storage import StorageCreateView, StorageUpdateView, StorageDeleteView


class GitStorageForm(SshStorageForm):
    ssh_url = CharField(required=True, label=_('Git Repository SSH Address'))
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
        url = fdroidserver.index.get_raw_mirror(form.cleaned_data['ssh_url'])
        if url is not None:
            form.instance.url = url
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
    template_name = 'maker/storage/form_git.html'

    # TODO make adding a two step process,
    #      so the user can add the SSH key before an upload is attempted

    def get_success_url(self):
        self.get_repo().update_async()
        return reverse_lazy('storage_git_detail',
                            kwargs={'repo_id': self.kwargs['repo_id'], 'pk': self.object.pk})


class GitStorageUpdate(GitUrlValidationMixin, StorageUpdateView):
    model = GitStorage
    form_class = GitStorageForm

    def get_success_url(self):
        self.get_repo().update_async()
        return reverse_lazy('storage_git_detail',
                            kwargs={'repo_id': self.kwargs['repo_id'], 'pk': self.kwargs['pk']})


class GitStorageDetail(DetailView):
    model = GitStorage
    template_name = 'maker/storage/detail_git.html'


class GitStorageDelete(StorageDeleteView):
    model = GitStorage
