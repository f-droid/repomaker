#!/usr/bin/env bash

python3 manage.py makemessages --keep-pot --no-wrap --no-location --no-obsolete --ignore node_modules -v 3
python3 manage.py makemessages --keep-pot --no-wrap --no-location --no-obsolete --ignore node_modules --ignore data -v 3 -d djangojs

sed -i -e '/^"POT-Creation-Date: /d' repomaker/locale/*/LC_MESSAGES/django.po
sed -i -e '/^"POT-Creation-Date: /d' repomaker/locale/*/LC_MESSAGES/djangojs.po

