from unittest.mock import patch

import os
from django.conf import settings
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from fdroidserver.exception import BuildException

from repomaker.models import App, Apk, ApkPointer, Repository
from repomaker.views.repository import RepositoryCreateView, RepositoryForm, RepositoryView
from .. import fake_repo_create, RmTestCase


class RepositoryTestCase(RmTestCase):

    def setUp(self):
        super().setUp()

        # create second user
        self.user = User.objects.create(username='user2')

        # create app in repo
        self.app = App.objects.create(repo=self.repo,
                                      package_id='org.bitbucket.tickytacky.mirrormirror',
                                      name='TestApp', website='TestSite', author_name='author')
        self.app.translate(settings.LANGUAGE_CODE)
        self.app.summary = 'TestSummary'
        self.app.description = 'TestDesc'
        self.app.save()

    def test_empty_state(self):
        # remove all repositories before we can test an empty state
        Repository.objects.all().delete()

        response = self.client.get(reverse('index'))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'repomaker/index.html')
        # TODO assert more things when implementing UI design

    @patch('fdroidserver.common.genkeystore')
    def test_create(self, genkeystore):
        # retrieve the add repo page
        response = self.client.get(reverse('add_repo'))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'repomaker/repo/add.html')
        self.assertTrue(isinstance(response.context['view'], RepositoryCreateView))
        self.assertContains(response, 'New Repo', 2)

        # fake keystore creation to speed up test
        genkeystore.return_value = 'TestPubKey', 'TestFingerprint'

        # post data for a new repository to be created
        query = {'name': 'TestRepo', 'description': 'TestDescription'}
        response = self.client.post(reverse('add_repo'), query)
        self.assertRedirects(response, '/2/')
        self.assertTrue(genkeystore.called)

        # assert that a new repository was created properly
        repositories = Repository.objects.all()
        self.assertEqual(2, len(repositories))
        repo = repositories[1]
        self.assertEqual(query['name'], repo.name)
        self.assertEqual(query['description'], repo.description)
        self.assertEqual('TestPubKey', repo.public_key)
        self.assertEqual('TestFingerprint', repo.fingerprint)

    @patch('fdroidserver.common.genkeystore')
    @patch('repomaker.models.repository.Repository._copy_page_assets')
    @override_settings(DEFAULT_REPO_STORAGE=[('repos', 'test')])
    def test_create_with_default_storage(self, _copy_page_assets, genkeystore):
        # fake keystore creation to speed up test
        genkeystore.return_value = 'TestPubKey', 'TestFingerprint'

        # post data for a new repository to be created
        query = {'name': 'TestRepo', 'description': 'TestDescription'}
        response = self.client.post(reverse('add_repo'), query)
        self.assertRedirects(response, '/2/')
        self.assertTrue(_copy_page_assets.called)

        # assert that a new repository was created properly
        repo = Repository.objects.get(pk=2)
        self.assertEqual('test/3h7jhCnUt8aFXubfAIXZgYSjLs0IWKEf/repo', repo.url)
        self.assertTrue(repo.qrcode)
        self.assertTrue(os.path.isfile(repo.qrcode.path))

    def test_create_no_name(self):
        # post incomplete data for a new repository to be created
        query = {'description': 'TestDescription'}
        response = self.client.post(reverse('add_repo'), query)
        self.assertEqual(200, response.status_code)

        # assert that we are on the same page with a form error
        self.assertTrue(isinstance(response.context['view'], RepositoryCreateView))
        self.assertTrue(isinstance(response.context['form'], RepositoryForm))
        self.assertFormError(response, 'form', 'name', 'This field is required.')

    def test_create_no_description(self):
        # post incomplete data for a new repository to be created
        query = {'name': 'TestRepo'}
        response = self.client.post(reverse('add_repo'), query)
        self.assertEqual(200, response.status_code)

        # assert that we are on the same page with a form error
        self.assertTrue(isinstance(response.context['view'], RepositoryCreateView))
        self.assertTrue(isinstance(response.context['form'], RepositoryForm))
        self.assertFormError(response, 'form', 'description', 'This field is required.')

    @patch('fdroidserver.common.genkeystore')
    def test_create_fails(self, genkeystore):
        # remember how many repositories we have
        repo_count = Repository.objects.all().count()

        # creating the key store will fail
        genkeystore.side_effect = BuildException('keystore failure')

        # post data for a new repository to be created
        query = {'name': 'TestRepo', 'description': 'TestDescription'}
        response = self.client.post(reverse('add_repo'), query)

        # assert that error message is shown
        self.assertContains(response, 'Error')
        self.assertContains(response, 'keystore failure')
        self.assertContains(response,
                            _('There was an error creating the repository. Please try again!'))

        # assert that repository was deleted
        self.assertEqual(repo_count, Repository.objects.all().count())

    def test_list(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'repomaker/index.html')

        # assert that context is as expected
        self.assertEqual(1, len(response.context['repositories']))
        self.assertEqual(self.repo, response.context['repositories'][0])

        # assert that page content is as expected
        self.assertContains(response, self.repo.name, 2)  # once in link title
        self.assertContains(response, self.repo.description, 1)

    def test_details(self):
        # Add fake fingerprint to repo for view to work
        self.repo.fingerprint = '28e14fb3b280bce8ff1e0f8e82726ff46923662cecff2a0689108ce19e8b347c'
        self.repo.save()

        # Retrieve the add repo page
        response = self.client.get(reverse('repo', kwargs={'repo_id': self.repo.id}))
        self.assertEqual(200, response.status_code)

        # Assert that we are in the right view with the correct templates
        self.assertTemplateUsed(response, 'repomaker/repo/index.html')
        self.assertTemplateUsed(response, 'repomaker/repo/index_apps.html')
        self.assertTemplateUsed(response, 'repomaker/repo/index_info.html')
        self.assertTemplateUsed(response, 'repomaker/repo/index_share.html')
        self.assertTrue(isinstance(response.context['view'], RepositoryView))
        self.assertEqual(self.repo, response.context['repo'])
        self.assertEqual(self.app, response.context['apps'][0])
        self.assertTrue(len(response.context['storage']) == 0)

        # Assert that all contents exist
        self.assertContains(response, self.repo.name, 3)
        self.assertContains(response, self.app.name, 1)
        self.assertContains(response, self.app.summary, 1)
        self.assertContains(response, self.app.description, 1)

        # TODO: Add tests for INFO and SHARE pages when design is implemented

    def test_details_app_translation(self):
        # Add fake fingerprint to repo for view to work
        self.repo.fingerprint = '28e14fb3b280bce8ff1e0f8e82726ff46923662cecff2a0689108ce19e8b347c'
        self.repo.save()

        # Add second app only available in German
        app2 = App.objects.create(repo=self.repo, package_id='org.example', name='App2')
        app2.translate('de')
        app2.summary = 'Test Zusammenfassung'
        app2.description = 'Test Beschreibung'
        app2.save()

        # Request repo app list page and ensure all localized descriptions are shown
        response = self.client.get(reverse('repo', kwargs={'repo_id': self.repo.id}))
        self.assertContains(response, self.app.summary)
        self.assertContains(response, self.app.description)
        self.assertContains(response, app2.description)
        self.assertContains(response, app2.description)

    def test_upload_apk_as_new_app(self):
        fake_repo_create(self.repo)
        self.repo.chdir()

        App.objects.all().delete()
        self.assertEqual(0, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(reverse('repo', kwargs={'repo_id': self.repo.id}), {'apks': f},
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_RM_BACKGROUND_TYPE='apks')

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())

        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_upload_apk_as_update(self):
        fake_repo_create(self.repo)
        self.repo.chdir()

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_1.apk'), 'rb') as f:
            self.client.post(reverse('repo', kwargs={'repo_id': self.repo.id}), {'apks': f},
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_RM_BACKGROUND_TYPE='apks')

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())

        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_upload_invalid_apk(self):
        fake_repo_create(self.repo)
        self.repo.chdir()

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test_invalid_signature.apk'), 'rb') as f:
            response = self.client.post(reverse('repo', kwargs={'repo_id': self.repo.id}),
                                        {'apks': f}, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                                        HTTP_RM_BACKGROUND_TYPE='apks')
        self.assertContains(response, 'test_invalid_signature.apk: Invalid APK signature',
                            status_code=500)

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        self.assertFalse(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_upload_non_apk(self):
        fake_repo_create(self.repo)
        self.repo.chdir()

        self.assertEqual(1, App.objects.all().count())
        self.assertEqual(0, Apk.objects.all().count())
        self.assertEqual(0, ApkPointer.objects.all().count())

        with open(os.path.join(settings.TEST_FILES_DIR, 'test.avi'), 'rb') as f:
            self.client.post(reverse('repo', kwargs={'repo_id': self.repo.id}), {'apks': f},
                             HTTP_X_REQUESTED_WITH='XMLHttpRequest', HTTP_RM_BACKGROUND_TYPE='apks')

        self.assertEqual(2, App.objects.all().count())
        self.assertEqual(1, Apk.objects.all().count())
        self.assertEqual(1, ApkPointer.objects.all().count())

        self.assertTrue(Repository.objects.get(pk=self.repo.pk).update_scheduled)

    def test_delete(self):
        response = self.client.post(reverse('delete_repo', kwargs={'repo_id': self.repo.id}))
        self.assertRedirects(response, '/')
        self.assertEqual(0, len(Repository.objects.all()))
