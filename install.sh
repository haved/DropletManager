#!/bin/bash -ex

apt-get update
apt-get upgrade -y
apt-get install -y openjdk-14-jdk apache2 maven python3 certbot python3-certbot-apache
#build-essential

# Setting up reverse proxy
# See: https://www.digitalocean.com/community/tutorials/how-to-use-apache-http-server-as-reverse-proxy-using-mod_proxy-extension
# See: https://www.digitalocean.com/community/tutorials/how-to-install-the-apache-web-server-on-ubuntu-20-04#step-5-%E2%80%94-setting-up-virtual-hosts-(recommended)

a2enmod proxy
a2enmod proxy_http
a2enmod proxy_ajp
a2enmod rewrite
a2enmod deflate
a2enmod headers
#a2enmod proxy_balancer
a2enmod proxy_connect
a2enmod proxy_html
a2enmod ssl

sed -i '1iServerName haved.no' /etc/apache2/apache2.conf
cp haved_apache.conf /etc/apache2/sites-available/
a2dissite 000-default.conf # disable
a2ensite haved_apache.conf

# Firewall settings
ufw allow 'Apache Full' #Needed for HTTPS
ufw allow 'Apache'
ufw allow 'OpenSSH'
ufw enable


# Prepare user for Gazelle Spring Boot server
useradd -d /home/gazellespring -s /sbin/nologin gazellespring
mkdir /home/gazellespring
chown gazellespring /home/gazellespring
chmod 700 /home/gazellespring

# Preparing folder for gazelle webapp
mkdir /var/www/html/gazelle


# Finally, start apache
systemctl start apache2
