FROM registry.gitlab.com/fdroid/ci-images-repomaker:latest
MAINTAINER team@f-droid.org

ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE repomaker.settings_docker
ENV REPOMAKER_SECRET_KEY "913d6#u8@-*#3l)spwzurd#fd77bey-6mfs5fc$a=yhnh!n4p9"

WORKDIR /repomaker

ADD . /repomaker

COPY docker/settings_docker.py ./repomaker/
COPY docker/apache.conf /etc/apache2/sites-available/repomaker.conf
COPY docker/wait-for ./
COPY docker/httpd-foreground ./

RUN apt update && \
	apt install openssh-client netcat gettext apache2 libapache2-mod-wsgi-py3 -y --no-install-recommends && \
	cat docker/ssh_config >> /etc/ssh/ssh_config && \
	a2dissite 000-default && \
	a2ensite repomaker && \
	pip3 install -r requirements.txt && \
	npm install && \
	./pre-release.sh

