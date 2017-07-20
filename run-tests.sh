#!/usr/bin/env bash

pep8 --show-pep8 --max-line-length=100 --exclude=setup.py,.git,build,migrations . &&
pylint --disable=C,R,fixme repomaker &&
coverage3 run --source='repomaker' --omit="*/wsgi.py","repomaker/__init__.py" manage.py test &&
coverage3 report &&
echo "All tests ran successfully! \o/"
