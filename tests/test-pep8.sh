#!/usr/bin/env bash

pycodestyle --show-pep8 --max-line-length=100 --exclude=setup.py,.git,build,migrations,docker,bin,lib .
