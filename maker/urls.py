from django.conf.urls import url

from maker.models import S3Storage, SshStorage, GitStorage
from maker.views.app import AppCreateView, AppDetailView, AppUpdateView, AppDeleteView, \
    AppTranslationUpdateView
from maker.views.gitstorage import GitStorageCreate, GitStorageUpdate, GitStorageDetail, \
    GitStorageDelete
from maker.views.remoterepository import RemoteRepositoryCreateView, RemoteAppCreateView
from maker.views.repository import RepositoryListView, RepositoryCreateView, RepositoryDetailView
from maker.views.s3storage import S3StorageCreate, S3StorageUpdate, S3StorageDelete
from maker.views.screenshot import ScreenshotCreateView, ScreenshotDeleteView
from maker.views.sshstorage import SshStorageCreate, SshStorageUpdate, SshStorageDetail, \
    SshStorageDelete
from . import views


urlpatterns = [
    # Repo
    url(r'^$', RepositoryListView.as_view(), name='index'),
    url(r'^add$', RepositoryCreateView.as_view(), name='add_repo'),
    url(r'^(?P<repo_id>[0-9]+)/$', RepositoryDetailView.as_view(), name='repo'),

    # Remote Repo
    url(r'^remote/add$', RemoteRepositoryCreateView.as_view(), name='add_remote_repo'),
    url(r'^remote/(?P<remote_repo_id>[0-9]+)/update/$', views.remote_update, name='remote_update'),

    # App
    url(r'^(?P<repo_id>[0-9]+)/app/add/$', AppCreateView.as_view(), name='add_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/remote/(?P<remote_repo_id>[0-9]+)/add/$',
        AppCreateView.as_view(), name='add_app_from_remote'),
    url(r'^(?P<repo_id>[0-9]+)/app/remote/(?P<remote_repo_id>[0-9]+)/add/(?P<app_id>[0-9]+)$',
        RemoteAppCreateView.as_view(), name='add_remote_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/$', AppDetailView.as_view(), name='app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/edit/$', AppUpdateView.as_view(),
        name='edit_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/delete/$', AppDeleteView.as_view(),
        name='delete_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/translate/$',
        AppTranslationUpdateView.as_view(), name='app_translate'),

    # App Screenshots
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/screenshot/add/$',
        ScreenshotCreateView.as_view(), name='screenshot_add'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/screenshot/(?P<s_id>[0-9]+)/delete/$',
        ScreenshotDeleteView.as_view(), name='screenshot_delete'),

    # Repo Operations
    url(r'^(?P<repo_id>[0-9]+)/update/$$', views.update, name='update'),
    url(r'^(?P<repo_id>[0-9]+)/publish/$$', views.publish, name='publish'),

    # SSH Storage
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/add/$',
        SshStorageCreate.as_view(), name='storage_ssh_add'),
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/(?P<pk>[0-9]+)/$',
        SshStorageUpdate.as_view(), name=SshStorage.edit_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/(?P<pk>[0-9]+)/detail$',
        SshStorageDetail.as_view(), name='storage_ssh_detail'),
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/(?P<pk>[0-9]+)/delete/$',
        SshStorageDelete.as_view(), name=SshStorage.delete_url_name),

    # Git Storage
    url(r'^(?P<repo_id>[0-9]+)/storage/git/add/$',
        GitStorageCreate.as_view(), name='storage_git_add'),
    url(r'^(?P<repo_id>[0-9]+)/storage/git/(?P<pk>[0-9]+)/$',
        GitStorageUpdate.as_view(), name=GitStorage.edit_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/git/(?P<pk>[0-9]+)/detail$',
        GitStorageDetail.as_view(), name='storage_git_detail'),
    url(r'^(?P<repo_id>[0-9]+)/storage/git/(?P<pk>[0-9]+)/delete/$',
        GitStorageDelete.as_view(), name=GitStorage.delete_url_name),

    # S3 Storage
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/add/$',
        S3StorageCreate.as_view(), name='storage_s3_add'),
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/(?P<pk>[0-9]+)/$',
        S3StorageUpdate.as_view(), name=S3Storage.edit_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/(?P<pk>[0-9]+)/delete/$',
        S3StorageDelete.as_view(), name=S3Storage.delete_url_name),
]
