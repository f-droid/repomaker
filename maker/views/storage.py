from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from maker.models import Repository


@method_decorator(login_required, name='dispatch')
class StorageCreateView(CreateView):

    def form_valid(self, form):
        repo_id = self.kwargs['repo_id']
        repo = get_object_or_404(Repository, pk=repo_id)
        if repo.user != self.request.user:
            return HttpResponseForbidden()
        form.instance.repo = repo
        return super(StorageCreateView, self).form_valid(form)

    def get_success_url(self):
        return get_success_url(self)


@method_decorator(login_required, name='dispatch')
class StorageUpdateView(UpdateView):

    def get_success_url(self):
        return get_success_url(self)


@method_decorator(login_required, name='dispatch')
class StorageDeleteView(DeleteView):

    def get_success_url(self):
        return get_success_url(self)


def get_success_url(view):
    return reverse_lazy('repo', kwargs={'repo_id': view.kwargs['repo_id']})
