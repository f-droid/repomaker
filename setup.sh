pip3 install -r requirements.txt && \
npm install && \
python3 manage.py makemigrations background_task && \
python3 manage.py makemigrations maker && \
python3 manage.py migrate && \
echo "All set up, now execute run.sh"

