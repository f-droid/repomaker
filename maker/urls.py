from django.conf.urls import url

from maker.views.repository import RepositoryListView, RepositoryCreateView, RepositoryDetailView
from maker.views.s3storage import S3StorageCreate, S3StorageUpdate, S3StorageDelete
from maker.views.sshstorage import SshStorageCreate, SshStorageUpdate, SshStorageDelete
from . import views


urlpatterns = [
    # Repo
    url(r'^$', RepositoryListView.as_view(), name='index'),
    url(r'^add$', RepositoryCreateView.as_view(), name='add_repo'),
    url(r'^(?P<repo_id>[0-9]+)/$', RepositoryDetailView.as_view(), name='repo'),
    # App
    url(r'^(?P<repo_id>[0-9]+)/app/add/$', views.add_app, name='add_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/$', views.show_app, name='app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/edit/$', views.edit_app, name='edit_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/delete/$', views.delete_app,
        name='delete_app'),
    # Repo Operations
    url(r'^(?P<repo_id>[0-9]+)/update/$$', views.update, name='update'),
    url(r'^(?P<repo_id>[0-9]+)/publish/$$', views.publish, name='publish'),
    # SSH Storage
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/add/$',
        SshStorageCreate.as_view(), name='storage_ssh_add'),
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/(?P<pk>[0-9]+)/$',
        SshStorageUpdate.as_view(), name='storage_ssh_update'),
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/(?P<pk>[0-9]+)/delete/$',
        SshStorageDelete.as_view(), name='storage_ssh_delete'),
    # S3 Storage
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/add/$',
        S3StorageCreate.as_view(), name='storage_s3_add'),
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/(?P<pk>[0-9]+)/$',
        S3StorageUpdate.as_view(), name='storage_s3_update'),
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/(?P<pk>[0-9]+)/delete/$',
        S3StorageDelete.as_view(), name='storage_s3_delete'),
]
