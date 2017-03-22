from django.contrib.auth.decorators import login_required
from django.forms import ModelForm, PasswordInput
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic.edit import CreateView, UpdateView, DeleteView

from maker.models import Repository, S3Storage


class S3StorageForm(ModelForm):
    class Meta:
        model = S3Storage
        fields = ['region', 'bucket', 'accesskeyid', 'secretkey']
        labels = {
            'bucket': 'Bucket Name',
            'accesskeyid': 'Access Key ID',
            'secretkey': 'Secret Access Key',
        }
        help_texts = {
            'region': 'Other regions are currently not supported.',
        }
        widgets = {
            'secretkey': PasswordInput(),
        }


@method_decorator(login_required, name='dispatch')
class S3StorageCreate(CreateView):
    model = S3Storage
    form_class = S3StorageForm

    def get_context_data(self, **kwargs):
        context = super(S3StorageCreate, self).get_context_data(**kwargs)
        context['repo_id'] = self.kwargs['repo_id']
        return context

    def form_valid(self, form):
        repo_id = self.kwargs['repo_id']
        repo = get_object_or_404(Repository, pk=repo_id)
        if repo.user != self.request.user:
            return HttpResponseForbidden()
        form.instance.repo = repo
        return super(S3StorageCreate, self).form_valid(form)

    def get_success_url(self):
        return reverse_lazy('repo', kwargs={'repo_id': self.kwargs['repo_id']})


@method_decorator(login_required, name='dispatch')
class S3StorageUpdate(UpdateView):
    model = S3Storage
    form_class = S3StorageForm

    def get_success_url(self):
        return reverse_lazy('repo', kwargs={'repo_id': self.kwargs['repo_id']})


@method_decorator(login_required, name='dispatch')
class S3StorageDelete(DeleteView):
    model = S3Storage

    def get_success_url(self):
        return reverse_lazy('repo', kwargs={'repo_id': self.kwargs['repo_id']})
