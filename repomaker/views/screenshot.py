from django.conf import settings
from django.forms import Select
from django.utils.translation import ugettext_lazy as _
from django.views.generic import DeleteView

from repomaker.models import Screenshot
from repomaker.views.repository import RepositoryAuthorizationMixin
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


class ScreenshotDeleteView(RepositoryAuthorizationMixin, DeleteView):
    model = Screenshot
    pk_url_kwarg = 's_id'
    template_name = 'repomaker/app/screenshot_delete.html'

    def get_repo(self):
        return self.get_object().app.repo

    def get_success_url(self):
        self.get_repo().update_async()
        return self.get_object().app.get_edit_url()
