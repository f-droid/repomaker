#!/usr/bin/env bash

# remove local files
rm -rf data/private_repo/user_*
rm -rf data/media/user_*
rm -rf data/media/remote_repo_*
rm -rf data/media/packages

# remove database and move custom migrations out of the way
rm repomaker/migrations/0*
mv repomaker/migrations/default_user.py repomaker/migrations/default_user.py.bak
mv repomaker/migrations/default_categories.py repomaker/migrations/default_categories.py.bak
mv repomaker/migrations/default_remote_repositories.py repomaker/migrations/default_remote_repositories.py.bak
rm data/db.sqlite3

# initialize database and re-add custom migrations
python3 manage.py makemigrations repomaker
mv repomaker/migrations/default_user.py.bak repomaker/migrations/default_user.py
mv repomaker/migrations/default_categories.py.bak repomaker/migrations/default_categories.py
mv repomaker/migrations/default_remote_repositories.py.bak repomaker/migrations/default_remote_repositories.py
python3 manage.py migrate
