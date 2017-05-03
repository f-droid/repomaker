"""RepoMaker URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin

from maker.views import media_serve
from maker.views.repository import RepositoryListView

urlpatterns = [
    url(r'^$', RepositoryListView.as_view(), name="index"),
    url(r'^repo/', include('maker.urls')),
    url(r'^admin/', admin.site.urls),
    url(r'^tinymce/', include('tinymce.urls')),
    url(r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:], media_serve,
        {'document_root': settings.MEDIA_ROOT}),
]

if not settings.SINGLE_USER_MODE:
    urlpatterns += [
        url(r'^accounts/', include('allauth.urls')),
    ]
