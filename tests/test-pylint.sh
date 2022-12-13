#!/usr/bin/env bash

export DJANGO_SETTINGS_MODULE=repomaker.settings_test
pylint --load-plugins=pylint_django --disable=C,R,fixme repomaker
