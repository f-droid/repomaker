import bleach
from unittest import TestCase

from repomaker.utils import clean


class UtilsTest(TestCase):

    def test_clean_empty_link(self):
        if bleach.__version__ == '3.2.1':
            self.skipTest('skipping since bleach v3.2.1 does not clean this properly')
        string = 'Link <a href="fdroid.app:org.torproject.android">Orbot</a> not supported'
        self.assertEqual('Link Orbot not supported', clean(string))

    def test_clean_only_empty_link(self):
        string = 'Link <a href="https://orbot.org">Orbot</a> is supported'
        self.assertEqual(string, clean(string))
