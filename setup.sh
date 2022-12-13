#!/usr/bin/env bash
set -x
set -e
pip3 install -r requirements.txt
mkdir -p data
python3 manage.py makemigrations repomaker
python3 manage.py migrate
npm install
echo "All set up, now execute run.sh"
