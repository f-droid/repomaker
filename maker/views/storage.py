from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from maker.models import Repository
from . import LoginOrSingleUserRequiredMixin


class StorageCreateView(LoginOrSingleUserRequiredMixin, CreateView):

    def form_valid(self, form):
        repo_id = self.kwargs['repo_id']
        repo = get_object_or_404(Repository, pk=repo_id)
        if repo.user != self.request.user:
            return HttpResponseForbidden()
        form.instance.repo = repo
        return super(StorageCreateView, self).form_valid(form)

    def get_success_url(self):
        return get_success_url(self)


class StorageUpdateView(LoginOrSingleUserRequiredMixin, UpdateView):

    def get_success_url(self):
        return get_success_url(self)


class StorageDeleteView(LoginOrSingleUserRequiredMixin, DeleteView):

    def get_success_url(self):
        return get_success_url(self)


def get_success_url(view):
    return reverse_lazy('repo', kwargs={'repo_id': view.kwargs['repo_id']})
