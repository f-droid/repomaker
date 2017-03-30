import urllib.parse

from maker.models import RemoteRepository, Repository
from . import BaseModelForm, LoginOrSingleUserRequiredMixin
from django.views.generic.edit import CreateView

from fdroidserver import index


class RemoteRepositoryForm(BaseModelForm):
    class Meta:
        model = RemoteRepository
        fields = ['url']
        labels = {
            'url': 'Repository URL',
        }


class RemoteRepositoryCreateView(LoginOrSingleUserRequiredMixin, CreateView):
    model = RemoteRepository
    form_class = RemoteRepositoryForm
    template_name = "maker/repo/add.html"

    def form_valid(self, form):
        # ensure that URL contains a fingerprint
        url = urllib.parse.urlsplit(form.instance.url)
        query = urllib.parse.parse_qs(url.query)
        if 'fingerprint' not in query:
            form.add_error('url', "Please use a URL with a fingerprint at the end" +
                           ", so we can validate the authenticity of the repository.")
            return self.form_invalid(form)

        # check if the user is trying to add their own repo here
        fingerprint = query['fingerprint'][0]
        if Repository.objects.filter(user=self.request.user,
                                     fingerprint=fingerprint).exists():
            form.add_error('url', "Please don't add one of your own repositories here.")
            return self.form_invalid(form)

        # download repo index
        form.instance.get_config()
        try:
            repo_index = index.download_repo_index(form.instance.url)
        except index.VerificationException as e:
            form.add_error('url', "Could not validate repository: %s" % e)
            return self.form_invalid(form)

        form.instance.name = repo_index['repo']['name']
        form.instance.description = repo_index['repo']['description']
        form.instance.last_change_date = repo_index['repo']['timestamp']
        form.instance.fingerprint = fingerprint
        form.instance.public_key = repo_index['repo']['pubkey']
        # TODO: download and store repo_index['repo']['icon']

        result = super(RemoteRepositoryCreateView, self).form_valid(form)
        form.instance.users.add(self.request.user)
        form.instance.save()
        return result
