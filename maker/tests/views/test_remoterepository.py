import os
import shutil

import django.http
import django.urls
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from maker.models import Repository, RemoteRepository, RemoteApp
from .. import TEST_DIR


class RemoteRepositoryViewTest(TestCase):

    def setUp(self):
        self.repo = Repository.objects.create(
            name="Test Name",
            description="Test Description",
            url="https://example.org",
            user=User.objects.all()[0],
        )
        self.remote_repo = RemoteRepository.objects.get(pk=1)

        self.app = RemoteApp.objects.create(repo=self.remote_repo, package_id='org.example',
                                            last_updated_date=self.remote_repo.last_updated_date,
                                            name='App')
        self.app.translate('de')
        self.app.l_summary = 'Test Summary'
        self.app.l_description = 'Test Description'
        self.app.save()

        # Add second app only available in German
        self.app2 = RemoteApp.objects.create(repo=self.remote_repo, package_id='org.example2',
                                             last_updated_date=self.remote_repo.last_updated_date,
                                             name='App2')
        self.app2.translate('de')
        self.app2.l_summary = 'Test Zusammenfassung'
        self.app2.l_description = 'Test Beschreibung'
        self.app2.save()

    def tearDown(self):
        if os.path.isdir(TEST_DIR):
            shutil.rmtree(TEST_DIR)

    def test_list_app_translation(self):
        # Request repo app list page and ensure all localized descriptions are shown
        response = self.client.get(reverse('add_app', kwargs={'repo_id': self.repo.id}))
        self.assertContains(response, self.app.l_summary)
        self.assertContains(response, self.app.l_description)
        self.assertContains(response, self.app2.l_description)
        self.assertContains(response, self.app2.l_description)

    def test_list_app_ajax_translation(self):
        # Request repo app list page via json and ensure all localized descriptions are included
        response = self.client.get(reverse('add_app', kwargs={'repo_id': self.repo.id}),
                                   HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertTrue(isinstance(response, django.http.JsonResponse))
        self.assertContains(response, self.app.l_summary)
        self.assertContains(response, self.app.l_description)
        self.assertContains(response, self.app2.l_description)
        self.assertContains(response, self.app2.l_description)
