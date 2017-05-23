import os
import shutil
import sys
from importlib import reload
from unittest.mock import patch

import django.urls
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings, modify_settings
from django.urls import reverse

from maker import DEFAULT_USER_NAME

from maker.models import App, Repository
from maker.views.repository import RepositoryCreateView, RepositoryForm, RepositoryDetailView
from .. import TEST_DIR, TEST_MEDIA_DIR, TEST_PRIVATE_DIR


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR, PRIVATE_REPO_ROOT=TEST_PRIVATE_DIR)
class RepositoryTestCase(TestCase):
    def setUp(self):
        # create second user
        self.user = User.objects.create(username='user2')

        # create repository for singe-user-mode
        self.repo = Repository.objects.create(
            name="Test Name",
            description="Test Description",
            url="https://example.org",
            user=User.objects.get(username=DEFAULT_USER_NAME),
        )

        # create app in repo
        self.app = App.objects.create(repo=self.repo,
                                      package_id='org.bitbucket.tickytacky.mirrormirror',
                                      name='TestApp', summary='TestSummary', description='TestDesc',
                                      website='TestSite', author_name='author')

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_empty_state(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'maker/index.html')
        # TODO assert more things when implementing UI design

    @patch('fdroidserver.common.genkeystore')
    def test_create(self, genkeystore):
        # retrieve the add repo page
        response = self.client.get(reverse('add_repo'))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, 'maker/repo/add.html')
        self.assertTrue(isinstance(response.context['view'], RepositoryCreateView))
        self.assertContains(response, 'New Repo', 2)

        # fake keystore creation to speed up test
        genkeystore.return_value = 'TestPubKey', 'TestFingerprint'

        # post data for a new repository to be created
        query = {'name': 'TestRepo', 'description': 'TestDescription'}
        response = self.client.post(reverse('add_repo'), query)
        self.assertRedirects(response, '/repo/2/')
        self.assertTrue(genkeystore.called)

        # assert that a new repository was created properly
        repositories = Repository.objects.all()
        self.assertEqual(2, len(repositories))
        repo = repositories[1]
        self.assertEqual(query['name'], repo.name)
        self.assertEqual(query['description'], repo.description)
        self.assertEqual('TestPubKey', repo.public_key)
        self.assertEqual('TestFingerprint', repo.fingerprint)

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

    @override_settings(SINGLE_USER_MODE=False)
    @modify_settings(INSTALLED_APPS={'append': ['allauth', 'allauth.socialaccount']})
    def test_details_multi(self):
        # Update URL conf with overridden settings
        reload(sys.modules[settings.ROOT_URLCONF])
        django.urls.clear_url_caches()

        # Login
        self.client.force_login(user=self.user)

        # Replace single- app and repo with multi-user-mode one
        self.repo.user = self.user

        self.test_details()

    def test_details(self):
        # Add fake fingerprint to repo for view to work
        self.repo.fingerprint = '28e14fb3b280bce8ff1e0f8e82726ff46923662cecff2a0689108ce19e8b347c'
        self.repo.save()

        # Retrieve the add repo page
        response = self.client.get(reverse('repo', kwargs={'repo_id': self.repo.id}))
        self.assertEqual(200, response.status_code)

        # Assert that we are in the right view with the correct templates
        self.assertTemplateUsed(response, 'maker/repo/index.html')
        self.assertTemplateUsed(response, 'maker/repo/index/apps.html')
        self.assertTemplateUsed(response, 'maker/repo/index/info.html')
        self.assertTemplateUsed(response, 'maker/repo/index/share.html')
        self.assertTrue(isinstance(response.context['view'], RepositoryDetailView))
        self.assertEqual(self.repo, response.context['repo'])
        self.assertEqual(self.app, response.context['apps'][0])
        self.assertTrue(len(response.context['storage']) == 0)

        # Assert that all contents exist
        self.assertContains(response, self.repo.name, 3)
        self.assertContains(response, self.app.name, 1)
        self.assertContains(response, self.app.summary, 1)
        self.assertContains(response, self.app.description, 1)

        # TODO: Add tests for INFO and SHARE pages when design is implemented
