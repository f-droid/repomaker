import urllib.parse

from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from fdroidserver import index

from maker.models import RemoteRepository, Repository
from . import BaseModelForm, LoginOrSingleUserRequiredMixin


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
        user = self.request.user

        # ensure that URL contains a fingerprint
        url = urllib.parse.urlsplit(form.instance.url)
        query = urllib.parse.parse_qs(url.query)
        if 'fingerprint' not in query:
            form.add_error('url', "Please use a URL with a fingerprint at the end" +
                           ", so we can validate the authenticity of the repository.")
            return self.form_invalid(form)

        # check if the user is trying to add their own repo here
        fingerprint = query['fingerprint'][0]
        if Repository.objects.filter(user=user, fingerprint=fingerprint).exists():
            form.add_error('url', "Please don't add one of your own repositories here.")
            return self.form_invalid(form)

        # update URL and fingerprint to final values
        new_url = urllib.parse.SplitResult(url.scheme, url.netloc, url.path, '', '')
        form.instance.url = new_url.geturl()
        form.instance.fingerprint = fingerprint

        # check if this remote repo already exists and if so, re-use it
        existing_repo_query = RemoteRepository.objects.filter(url=form.instance.url,
                                                              fingerprint=fingerprint)
        if existing_repo_query.exists():
            existing_repo = existing_repo_query.get()
            existing_repo.users.add(user)
            existing_repo.save()
            return HttpResponseRedirect(self.get_success_url())

        # download repo index and apply information to instance
        try:
            form.instance.update_index()
        except index.VerificationException as e:
            form.add_error('url', "Could not validate repository: %s" % e)
            return self.form_invalid(form)

        result = super(RemoteRepositoryCreateView, self).form_valid(form)
        form.instance.users.add(user)
        form.instance.save()
        return result

    def get_success_url(self):
        # TODO point this to some sort of remote repo overview or detail view
        return reverse_lazy('index')
