# Docker Compose Deployment

First, copy the files `docker-compose.yml` and `.env` from this directory:

``` bash
cp docker/docker-compose.yml docker/.env .
```

Decide on which domain name your repomaker instance will be running.
Then edit your `.env` file:

 - Set up the database authentication, or disable it using [`POSTGRES_HOST_AUTH_METHOD=trust`](https://djangoforprofessionals.com/postgresql/#postgresql).
 - `REPOMAKER_HOSTNAME` Set your hostname, i.e `localhost`, `repomaker.domain.tld`, ...
 - `REPOMAKER_PORT` Leave it as default (80), or set another port if you get a port conflict.
 - `REPOMAKER_SECRET_KEY` Generate a new secret key for your deployment, for example like so:
``` bash
echo "REPOMAKER_SECRET_KEY=$(cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1)"
```



Then start the docker containers:

```
docker-compose up
```

If everything worked as it should,
there should now be a repomaker instance running on your domain name.
