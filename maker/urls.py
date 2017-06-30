from django.conf.urls import url

from maker.models import S3Storage, SshStorage, GitStorage
from maker.views.app import AppAddView, AppDetailView, AppUpdateView, AppDeleteView, \
    AppTranslationUpdateView
from maker.views.gitstorage import GitStorageCreate, GitStorageUpdate, GitStorageDetail, \
    GitStorageDelete
from maker.views.remoterepository import RemoteRepositoryCreateView, RemoteAppCreateView
from maker.views.repository import RepositoryListView, RepositoryCreateView, RepositoryView, \
    RepositoryUpdateView, RepositoryDeleteView
from maker.views.s3storage import S3StorageCreate, S3StorageDetail, S3StorageUpdate, S3StorageDelete
from maker.views.screenshot import ScreenshotCreateView, ScreenshotDeleteView
from maker.views.sshstorage import SshStorageCreate, SshStorageUpdate, SshStorageDetail, \
    SshStorageDelete
from maker.views.apk import ApkUploadView, ApkPointerDeleteView
from maker.views.storage import StorageAddView
from . import views


urlpatterns = [
    # Repo
    url(r'^$', RepositoryListView.as_view(), name='index'),
    url(r'^add$', RepositoryCreateView.as_view(), name='add_repo'),
    url(r'^(?P<repo_id>[0-9]+)/$', RepositoryView.as_view(), name='repo'),
    url(r'^(?P<repo_id>[0-9]+)/edit/$', RepositoryUpdateView.as_view(),
        name='edit_repo'),
    url(r'^(?P<repo_id>[0-9]+)/delete/$', RepositoryDeleteView.as_view(),
        name='delete_repo'),

    # Remote Repo
    url(r'^remote/add$', RemoteRepositoryCreateView.as_view(), name='add_remote_repo'),
    url(r'^remote/(?P<remote_repo_id>[0-9]+)/update/$', views.remote_update, name='remote_update'),

    # App
    url(r'^(?P<repo_id>[0-9]+)/app/add/$', AppAddView.as_view(), name='add_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/remote/(?P<remote_repo_id>[0-9]+)/add/$',
        AppAddView.as_view(), name='add_app'),
    url(r'^(?P<repo_id>[0-9]+)/app/add/category/(?P<category_id>[0-9]+)/$',
        AppAddView.as_view(), name='add_app_with_category'),
    url(r'^(?P<repo_id>[0-9]+)/app/remote/(?P<remote_repo_id>[0-9]+)/add/' +
        r'category/(?P<category_id>[0-9]+)/$',
        AppAddView.as_view(), name='add_app_with_category'),
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

    # Apks
    url(r'^(?P<repo_id>[0-9]+)/app/apk/upload/$', ApkUploadView.as_view(), name='apk_upload'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/apk/(?P<pk>[0-9]+)/delete/$',
        ApkPointerDeleteView.as_view(), name='apk_delete'),

    # Repo Operations
    url(r'^(?P<repo_id>[0-9]+)/update/$$', views.update, name='update'),
    url(r'^(?P<repo_id>[0-9]+)/publish/$$', views.publish, name='publish'),

    # Storages
    url(r'^(?P<repo_id>[0-9]+)/storage/add/$',
        StorageAddView.as_view(), name='storage_add'),

    # S3 Storage
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/add/$',
        S3StorageCreate.as_view(), name=S3Storage.add_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/(?P<pk>[0-9]+)/$',
        S3StorageDetail.as_view(), name=S3Storage.detail_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/(?P<pk>[0-9]+)/edit/$',
        S3StorageUpdate.as_view(), name=S3Storage.edit_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/s3/(?P<pk>[0-9]+)/delete/$',
        S3StorageDelete.as_view(), name=S3Storage.delete_url_name),

    # SSH Storage
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/add/$',
        SshStorageCreate.as_view(), name=SshStorage.add_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/(?P<pk>[0-9]+)/$',
        SshStorageDetail.as_view(), name=SshStorage.detail_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/(?P<pk>[0-9]+)/edit/$',
        SshStorageUpdate.as_view(), name=SshStorage.edit_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/ssh/(?P<pk>[0-9]+)/delete/$',
        SshStorageDelete.as_view(), name=SshStorage.delete_url_name),

    # Git Storage
    url(r'^(?P<repo_id>[0-9]+)/storage/git/add/$',
        GitStorageCreate.as_view(), name=GitStorage.add_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/git/(?P<pk>[0-9]+)/$',
        GitStorageDetail.as_view(), name=GitStorage.detail_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/git/(?P<pk>[0-9]+)/edit/$',
        GitStorageUpdate.as_view(), name=GitStorage.edit_url_name),
    url(r'^(?P<repo_id>[0-9]+)/storage/git/(?P<pk>[0-9]+)/delete/$',
        GitStorageDelete.as_view(), name=GitStorage.delete_url_name),
]
