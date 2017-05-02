from django.conf import settings
from django.forms import Select
from django.urls import reverse, reverse_lazy
from django.utils.translation import ugettext_lazy as _
from django.views.generic import CreateView, DeleteView

from maker.models import Screenshot
from maker.views.repository import RepositoryAuthorizationMixin
from . import BaseModelForm


class ScreenshotForm(BaseModelForm):
    class Meta:
        model = Screenshot
        fields = ['language_code', 'type', 'file']
        labels = {
            'language_code': _('Language'),
            'file': _('Select Screenshot for upload'),
        }
        widgets = {
            'language_code': Select(choices=settings.LANGUAGES)
        }


class ScreenshotCreateView(RepositoryAuthorizationMixin, CreateView):
    model = Screenshot
    form_class = ScreenshotForm
    template_name = "maker/app/screenshot_add.html"

    def form_valid(self, form):
        form.instance.app_id = self.kwargs['app_id']
        result = super(ScreenshotCreateView, self).form_valid(form)
        self.get_repo().update_async()
        return result

    def get_success_url(self):
        return reverse('app', args=[self.object.app.repo.pk, self.object.app.pk])


class ScreenshotDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = Screenshot
    pk_url_kwarg = 's_id'
    template_name = 'maker/app/screenshot_delete.html'

    def get_repo(self):
        return self.get_object().app.repo

    def get_success_url(self):
        self.get_repo().update_async()
        return reverse_lazy('app', kwargs={'repo_id': self.kwargs['repo_id'],
                                           'app_id': self.kwargs['app_id']})
