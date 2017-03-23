from django.contrib import admin

from .models import Repository, SshStorage, S3Storage, App, Apk

admin.site.register(Repository)
admin.site.register(SshStorage)
admin.site.register(S3Storage)
admin.site.register(App)
admin.site.register(Apk)
