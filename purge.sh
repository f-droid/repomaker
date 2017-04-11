#!/usr/bin/env bash

# remove local files
rm -r private_repo/user_*
rm -r media/user_*
rm -r media/remote_repo_*
rm -r media/packages

# remove database and move custom migrations out of the way
rm maker/migrations/0*
mv maker/migrations/default_user.py maker/migrations/default_user.py.bak
mv maker/migrations/default_categories.py maker/migrations/default_categories.py.bak
mv maker/migrations/default_remote_repositories.py maker/migrations/default_remote_repositories.py.bak
rm db.sqlite3

# initialize database and re-add custom migrations
python3 manage.py makemigrations maker
mv maker/migrations/default_user.py.bak maker/migrations/default_user.py
mv maker/migrations/default_categories.py.bak maker/migrations/default_categories.py
mv maker/migrations/default_remote_repositories.py.bak maker/migrations/default_remote_repositories.py
python3 manage.py migrate

