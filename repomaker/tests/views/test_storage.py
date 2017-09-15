import os

from django.conf import settings
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from repomaker.models import S3Storage, SshStorage, GitStorage

from .. import RmTestCase


class StorageViewsTestCase(RmTestCase):

    def test_storage_add(self):
        kwargs = {'repo_id': self.repo.id}
        response = self.client.get(reverse('storage_add', kwargs=kwargs))

        self.assertContains(response, reverse(S3Storage.add_url_name, kwargs=kwargs))
        self.assertContains(response, reverse(SshStorage.add_url_name, kwargs=kwargs))
        self.assertContains(response, reverse(GitStorage.add_url_name, kwargs=kwargs))

    def test_storage_git_add(self):
        self.storage_git_add(True)

    def test_storage_git_add_local_key(self):
        self.storage_git_add(False)

    def storage_git_add(self, create_key):
        # Request form
        kwargs = {'repo_id': self.repo.id}
        response = self.client.get(reverse(GitStorage.add_url_name, kwargs=kwargs))

        # Check that form is shown as expected
        self.assertEqual(200, response.status_code)
        self.assertEqual(_('Git Storage'), response.context['storage_name'])
        self.assertEqual(self.repo, response.context['repo'])
        self.assertTrue('ssh_url' in response.context['form'].fields)
        self.assertTrue('url' in response.context['form'].fields)
        self.assertTrue('main' in response.context['form'].fields)

        # User submits empty form
        response = self.client.post(reverse(GitStorage.add_url_name, kwargs=kwargs), {})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.context['form'].has_error('ssh_url'))

        self.assertEqual(0, GitStorage.objects.all().count())

        # User submits wrong ssh_url
        response = self.client.post(reverse(GitStorage.add_url_name, kwargs=kwargs),
                                    {'ssh_url': 'test'})
        self.assertEqual(200, response.status_code)
        self.assertTrue(response.context['form'].has_error('ssh_url'))

        # User submits proper ssh_url
        response = self.client.post(reverse(GitStorage.add_url_name, kwargs=kwargs),
                                    {'ssh_url': 'git@gitlab.com:test/test.git',
                                     'ignore_identity_file': not create_key})
        self.assertEqual(1, GitStorage.objects.all().count())
        storage = GitStorage.objects.get()
        self.assertRedirects(response, storage.get_absolute_url())

        # Assert that git storage has been created properly
        self.assertEqual('gitlab.com', storage.host)
        self.assertEqual('test/test', storage.path)
        self.assertEqual('https://gitlab.com/test/test/raw/master/fdroid', storage.url)
        if create_key and settings.SINGLE_USER_MODE:
            self.assertTrue(storage.identity_file)
            self.assertTrue(os.path.isfile(storage.identity_file.path))
            self.assertTrue(len(storage.public_key) > 700)
        else:
            self.assertFalse(storage.identity_file)
        self.assertTrue(storage.disabled)

        # remove identity file again, workaround for not writing into PRIVATE_REPO_ROOT
        storage.identity_file.delete()

    def test_storage_git_edit(self):
        # Create Storage
        storage = GitStorage.objects.create(repo=self.repo, host='gitlab.com', path='test/test',
                                            url='test')

        # Request form
        kwargs = {'repo_id': self.repo.id, 'pk': storage.pk}
        response = self.client.get(reverse(GitStorage.edit_url_name, kwargs=kwargs))

        # Check that form is shown as expected
        self.assertEqual(200, response.status_code)
        self.assertEqual(_('Git Storage'), response.context['storage_name'])
        self.assertEqual(self.repo, response.context['repo'])
        self.assertTrue('ssh_url' in response.context['form'].fields)
        self.assertTrue('url' in response.context['form'].fields)
        self.assertTrue('main' in response.context['form'].fields)
        self.assertFalse('ignore_identity_file' in response.context['form'].fields)

        # Check that form is populated correctly
        self.assertEqual('test', response.context['form']['url'].value())
        self.assertEqual('git@gitlab.com:test/test.git',
                         response.context['form']['ssh_url'].value())
        self.assertEqual(False, response.context['form']['main'].value())

        # Change fields
        response = self.client.post(reverse(GitStorage.edit_url_name, kwargs=kwargs),
                                    {'ssh_url': 'git@gitlab.com:test2/test2.git'})
        self.assertRedirects(response, storage.get_absolute_url())

        # Assert that storage was changed as expected
        storage = GitStorage.objects.get()
        self.assertEqual('gitlab.com', storage.host)
        self.assertEqual('test2/test2', storage.path)
        self.assertEqual('https://gitlab.com/test2/test2/raw/master/fdroid', storage.url)
