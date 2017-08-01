#!/usr/bin/env bash

coverage3 run --source='repomaker' --omit="*/wsgi.py","repomaker/__init__.py" manage.py test &&
coverage3 report
