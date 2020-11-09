## Creating a user

This is not required, I just don't want to log in as root.

When creating the droplet I provided my `ssh_id.pub` instead of creating a root password.
This allows me to log into `root` using ssh authentication.
It also disables password login in the SSH configuration.

First create the user, give it a password (for sudo, not ssh)
```
adduser haved
usermod -aG sudo haved
```

Copy you authorized key to the new user
```
mkdir /home/haved/.ssh
cp /root/.ssh/authorized_keys /home/haved/.ssh/
```

Tell SSH to deny password login, and deny root login
```
nano /etc/ssh/ssh_config
========================
PermitRootLogin no
PasswordAuthentication no
ChallengeResponseAuthentication no
UsePAM no
```


