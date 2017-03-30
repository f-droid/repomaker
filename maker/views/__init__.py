from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.forms import ModelForm
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404

from maker import DEFAULT_USER_NAME
from maker.models import Repository


# TODO remove when not needed anymore for testing
def update(request, repo_id):
    repo = get_object_or_404(Repository, pk=repo_id)
    if repo.user != request.user:
        return HttpResponseForbidden()

    repo.update_async()
    return HttpResponse("Updated")


# TODO remove when not needed anymore for testing
def publish(request, repo_id):
    repo = get_object_or_404(Repository, pk=repo_id)
    if repo.user != request.user:
        return HttpResponseForbidden()

    repo.publish()
    return HttpResponse("Published")


class BaseModelForm(ModelForm):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('label_suffix', ':')  # TODO remove ':'
        super(BaseModelForm, self).__init__(*args, **kwargs)


class LoginOrSingleUserRequiredMixin(LoginRequiredMixin):
    """
    Mixin that should be used for all class-based views within this project.
    It verifies that the current user is authenticated
    or logs in the default user in single-user mode.
    """

    def dispatch(self, request, *args, **kwargs):
        if settings.SINGLE_USER_MODE and not request.user.is_authenticated:
            user = User.objects.get(username=DEFAULT_USER_NAME)
            login(request, user)
        return super().dispatch(request, *args, **kwargs)
