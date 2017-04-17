#!/usr/bin/env bash
set -x
pip3 install -r requirements.txt --user && \
python3 manage.py makemigrations maker && \
python3 manage.py migrate && \
echo "All set up, now execute run.sh"

