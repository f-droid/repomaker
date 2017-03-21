from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^add$', views.add_repo, name='add_repo'),
    url(r'^(?P<repo_id>[0-9]+)/$', views.show_repo, name='repo'),
    url(r'^(?P<repo_id>[0-9]+)/app/add', views.add_app, name='add_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/$', views.show_app, name='app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/edit', views.edit_app, name='edit_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/delete', views.delete_app, name='delete_app'),
    url(r'^(?P<repo_id>[0-9]+)/update$', views.update, name='update'),
    url(r'^(?P<repo_id>[0-9]+)/publish$', views.publish, name='publish'),
]
