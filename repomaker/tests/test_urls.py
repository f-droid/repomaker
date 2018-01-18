from django.contrib.auth.models import User
from django.urls import reverse, RegexURLResolver

import repomaker.storage
from repomaker.models import Repository, RemoteRepository, App, Category, Screenshot, Apk, \
    ApkPointer, GitStorage
from repomaker.tests import RmTestCase
from repomaker.urls import urlpatterns

IGNORE = ['js_reverse', 'javascript-catalog']


class UrlsTest(RmTestCase):
    test_user = None
    test_repo = None
    remote_repo = None
    category = None
    app = None
    screenshot = None
    apk = None
    apk_pointer = None
    storage = None

    def setUp(self):
        super().setUp()
        self.test_user = User.objects.create(username="testuser")
        self.test_repo = Repository.objects.create(
            name="Test Repo",
            description="This repo belongs to testuser, but another user is logged in.",
            url="https://example.org",
            user=self.test_user,
        )
        self.remote_repo = RemoteRepository.objects.get(pk=1)
        self.remote_repo.users = [self.test_user]
        self.remote_repo.save()
        self.category = Category.objects.create(user=self.test_user, name="TestCat")
        self.app = App.objects.create(repo=self.test_repo, package_id='org.example', name="App")
        self.screenshot = Screenshot.objects.create(app=self.app)
        self.apk = Apk.objects.create(package_id='org.example')
        self.apk_pointer = ApkPointer.objects.create(apk=self.apk, repo=self.test_repo,
                                                     app=self.app)
        self.storage = GitStorage.objects.create(repo=self.test_repo)

    def test_authentication(self):
        for url in urlpatterns:
            if isinstance(url, RegexURLResolver) or url.name in IGNORE:
                continue
            keys = url.regex.groupindex.keys()
            params = {}
            expectation = 403

            # Set URL parameters
            if 'repo_id' in keys:
                params['repo_id'] = self.test_repo.pk
            if 'remote_repo_id' in keys:
                params['remote_repo_id'] = self.remote_repo.pk
            if 'lang' in keys:
                params['lang'] = 'en-US'
            if 'category_id' in keys:
                params['category_id'] = self.category.pk
            if 'app_id' in keys:
                params['app_id'] = self.app.pk
            if 's_id' in keys:
                params['s_id'] = self.screenshot.pk
            if 'pk' in keys:
                params['pk'] = self.apk_pointer.pk
            if 'path' in keys:
                params['path'] = repomaker.storage.get_repo_root_path(self.test_repo)

            # Adapt HTTP status code expectations different from 403 Forbidden
            if 'index' == url.name:
                expectation = 200  # showing an index is always possible
            elif 'add_repo' == url.name or 'add_remote_repo' == url.name:
                expectation = 200  # adding a new (remote) repo is always possible
            elif 'app' == url.name or 'app_edit' == url.name:
                expectation = 404  # apps are bound to repo and return 404 when not found there

            resolved_url = reverse(url.name, kwargs=params)
            print("%(url)s should return %(status_code)d" % {'url': resolved_url,
                                                             'status_code': expectation})
            response = self.client.get(resolved_url)
            self.assertEqual(expectation, response.status_code)
