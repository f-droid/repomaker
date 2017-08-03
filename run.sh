#!/usr/bin/env bash

python3 manage.py runserver &
PID=$!
sleep 10
python3 manage.py process_tasks
pkill -P $PID
kill $PID
