python3 manage.py runserver &
PID=$!
python3 manage.py process_tasks
pkill -P $PID
kill $PID
