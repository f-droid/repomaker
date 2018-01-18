from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.views.i18n import javascript_catalog
from django_js_reverse.views import urls_js

from repomaker.models import S3Storage, SshStorage, GitStorage
from repomaker.views import media_serve
from repomaker.views.apk import ApkUploadView, ApkPointerDeleteView
from repomaker.views.app import AppDetailView, AppDeleteView, AppEditView, \
    AppTranslationCreateView, AppFeatureGraphicDeleteView
from repomaker.views.gitstorage import GitStorageCreate, GitStorageUpdate, GitStorageDetail, \
    GitStorageDelete
from repomaker.views.remoterepository import RemoteRepositoryCreateView, AppRemoteAddView, \
    RemoteAppImportView, RemoteAppImportViewScreenshots
from repomaker.views.repository import RepositoryCreateView, RepositoryView, RepositoryUpdateView, \
    RepositoryDeleteView, RepositoryListView
from repomaker.views.s3storage import S3StorageCreate, S3StorageDetail, S3StorageUpdate, \
    S3StorageDelete
from repomaker.views.screenshot import ScreenshotDeleteView
from repomaker.views.sshstorage import SshStorageCreate, SshStorageUpdate, SshStorageDetail, \
    SshStorageDelete
from repomaker.views.storage import StorageAddView
from . import views

js_info_dict = {
    'domain': 'djangojs',
    'packages': ('repomaker.apps.RepoMakerConfig',),
}

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^tinymce/', include('tinymce.urls')),
    url(r'^jsreverse/$', urls_js, name='js_reverse'),
    url(r'^%s(?P<path>.*)$' % settings.MEDIA_URL[1:], media_serve,
        {'document_root': settings.MEDIA_ROOT}, name='media'),

    # JavaScript Internationalisation
    url(r'^jsi18n/$', javascript_catalog, js_info_dict, name='javascript-catalog'),

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
    url(r'^(?P<repo_id>[0-9]+)/app/add/$', AppRemoteAddView.as_view(), name='add_app'),
    url(r'^(?P<repo_id>[0-9]+)/remote-app/(?P<remote_repo_id>[0-9]+)/add/$',
        AppRemoteAddView.as_view(), name='add_app'),
    url(r'^(?P<repo_id>[0-9]+)/remote-app/add/category/(?P<category_id>[0-9]+)/$',
        AppRemoteAddView.as_view(), name='add_app_with_category'),
    url(r'^(?P<repo_id>[0-9]+)/remote-app/(?P<remote_repo_id>[0-9]+)/add/' +
        r'category/(?P<category_id>[0-9]+)/$',
        AppRemoteAddView.as_view(), name='add_app_with_category'),
    # Remote App Details
    url(r'^(?P<repo_id>[0-9]+)/remote-app/(?P<remote_repo_id>[0-9]+)/(?P<app_id>[0-9]+)' +
        r'/lang/(?P<lang>[a-zA-Z_-]+)/$',
        RemoteAppImportView.as_view(), name='add_remote_app'),
    url(r'^(?P<repo_id>[0-9]+)/remote-app/(?P<remote_repo_id>[0-9]+)/(?P<app_id>[0-9]+)' +
        r'/lang/(?P<lang>[a-zA-Z_-]+)/screenshots/$',
        RemoteAppImportViewScreenshots.as_view(), name='add_remote_app_screenshots'),
    # App Detail and Edit
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/$', AppDetailView.as_view(), name='app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/lang/(?P<lang>[a-zA-Z_-]+)/$',
        AppDetailView.as_view(), name='app'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/lang/(?P<lang>[a-zA-Z_-]+)/edit/$',
        AppEditView.as_view(), name='app_edit'),
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/add/lang/$',
        AppTranslationCreateView.as_view(), name='app_add_lang'),
    # App Delete
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/delete/$', AppDeleteView.as_view(),
        name='delete_app'),
    # Feature Graphic Delete
    url(r'^(?P<repo_id>[0-9]+)/app/(?P<app_id>[0-9]+)/feature_graphic/delete/$',
        AppFeatureGraphicDeleteView.as_view(), name='delete_feature_graphic'),

    # App Screenshots
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

if not settings.SINGLE_USER_MODE:
    urlpatterns += [
        url(r'^accounts/', include('allauth.urls')),
    ]
