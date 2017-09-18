# Hosted

Repomaker can be run on a server in hosted mode.
Set `SINGLE_USER_MODE` to `False` in the settings.

## Enabling Remote Storage

Publishing to remote storages uses SSH.
For this to work, the user running the background tasks
needs to have the remote server's key in its  `.ssh/known_hosts` file.

