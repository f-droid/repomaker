from django.contrib import admin

from .models import RemoteRepository, Repository, SshStorage, S3Storage, App, RemoteApp, Apk, Category

admin.site.register(RemoteRepository)
admin.site.register(Repository)
admin.site.register(SshStorage)
admin.site.register(S3Storage)
admin.site.register(App)
admin.site.register(RemoteApp)
admin.site.register(Apk)
admin.site.register(Category)
