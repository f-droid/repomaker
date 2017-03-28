rm -r localrepo/user*
rm -r media/user*
rm maker/migrations/0*
mv maker/migrations/default_user.py maker/migrations/default_user.py.bak
mv maker/migrations/default_categories.py maker/migrations/default_categories.py.bak
rm db.sqlite3
python3 manage.py makemigrations maker
mv maker/migrations/default_user.py.bak maker/migrations/default_user.py
mv maker/migrations/default_categories.py.bak maker/migrations/default_categories.py
python3 manage.py migrate

