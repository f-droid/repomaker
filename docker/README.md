# Docker Compose Deployment

First download the files `docker-compose.yml` and `.env` from this directory.

Decide on which domain name your repomaker instance will be running.
Then generate a new secret key for your deployment.
For example like so:

    echo "REPOMAKER_SECRET_KEY=$(pwgen -cny 64 1)"

Edit the downloaded file `.env` and put your domain name and your secret key there.

Then start the docker containers:

    docker-compose up

If everything worked as it should,
there should now be a repomaker instance running on your domain name.

