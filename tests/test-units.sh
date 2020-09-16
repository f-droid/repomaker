#!/usr/bin/env bash

coverage=coverage
if which python3-coverage; then
    coverage=python3-coverage
elif which coverage3; then
    coverage=coverage3
fi

$coverage run --source='repomaker' --omit="*/wsgi.py","repomaker/__init__.py" manage.py test --settings repomaker.settings_test &&
$coverage run --append --source='repomaker' --omit="*/wsgi.py","repomaker/__init__.py" manage.py test --settings repomaker.settings_test_multi_user &&
$coverage report
