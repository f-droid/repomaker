rm -r localrepo/user*
rm -r media/user*
rm maker/migrations/0*
rm db.sqlite3
./manage.py makemigrations maker
./manage.py migrate
./manage.py createsuperuser

