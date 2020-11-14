# DropletManager

This repository contains a recipie for preparing a fresh droplet for my personal projects,
and a piece of software that will listen for updates announced via web hooks when projects are updated.

## Intalling

I'm starting from a fresh 1vCPU 1GB/25GB Ubuntu 20.04 LTS on Digital Ocean.

While not important, I decided to [make a user](./MakeUser.md) for myself, and disable root login / password login.

To start, clone the manager into your home folder and run `./install.sh`
```
git clone https://github.com/haved/DropletManager.git
cd DropletManager
sudo ./install.sh
```

This will install apache and other dependencies, as well as create sandbox users.
Apache is used to serve content, but also as a reverse proxy with HTTPS.

To enable HTTPS, run this certbot command (based on [this guide](https://www.digitalocean.com/community/tutorials/how-to-secure-apache-with-let-s-encrypt-on-ubuntu-20-04)).
```
certbot --apache
```
I selected every domain, and enabled HTTPS redirect. This will make a copy of `haved_apache.conf` with ports changed to `443`, and add `RewriteRules`

## Providing secrets

The manager or other programs may need secrets to run. You can provide them as environment variables
by pasting them into `secrets.sh`. See `secrets_template.sh` for what secrets are needed.

## Setting up autostart
Copy the file `manager.service` to systemd. Make sure the path inside matches where you cloned git!
This will lanuch `autostart.sh` on bootup, which in turn will start a detached tmux session with the manager.
The systemd service also supports stopping / restarting the tmux session.
```
sudo cp manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable manager.service
sudo systemctl start manager.service
```

## Attaching to the terminal
The manager is run inside a tmux session with root privileges.
```
sudo tmux attach -t manager
```
Use `Ctrl-B` `D` to leave
