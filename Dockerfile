FROM registry.gitlab.com/fdroid/ci-images-repomaker:latest
MAINTAINER team@f-droid.org

ENV PYTHONUNBUFFERED 1

WORKDIR /repomaker

ADD . /repomaker

RUN apt update && apt install netcat -y && \
	pip3 install -r requirements.txt && \
	npm install

COPY docker/settings_docker.py ./repomaker/
COPY docker/wait-for ./

