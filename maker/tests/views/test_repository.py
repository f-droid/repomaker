import os
import shutil
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from maker.models import Repository
from maker.views.repository import RepositoryCreateView, RepositoryForm
from .. import TEST_DIR, TEST_MEDIA_DIR, TEST_PRIVATE_DIR


@override_settings(MEDIA_ROOT=TEST_MEDIA_DIR, PRIVATE_REPO_ROOT=TEST_PRIVATE_DIR)
class RepositoryTestCase(TestCase):

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
        self.assertRedirects(response, '/repo/1/')
        self.assertTrue(genkeystore.called)

        # assert that a new repository was created properly
        repositories = Repository.objects.all()
        self.assertEqual(1, len(repositories))
        repo = repositories[0]
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
