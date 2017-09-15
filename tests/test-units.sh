#!/usr/bin/env bash

coverage3 run --source='repomaker' --omit="*/wsgi.py","repomaker/__init__.py" manage.py test &&
coverage3 run --append --source='repomaker' --omit="*/wsgi.py","repomaker/__init__.py" manage.py test --settings repomaker.settings_test_multi_user &&
coverage3 report
