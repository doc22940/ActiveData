
# FOR AMAZON AMI ONLY
# ENSURE THE EC2 INSTANCE IS GIVEN A ROLE THAT ALLOWS IT ACCESS TO S3 AND DISCOVERY
# THIS EXAMPLE WORKS, BUT YOU MAY FIND IT TOO PERMISSIVE
# {
#   "Version": "2012-10-17",
#   "Statement": [
#     {
#       "Effect": "Allow",
#       "NotAction": "iam:*",
#       "Resource": "*"
#     }
#   ]
# }


# NOTE: NODE DISCOVERY WILL ONLY WORK IF PORT 9300 IS OPEN BETWEEN THEM

sudo yum -y update


# SETUP EPHEMERAL DRIVE

sudo mount /dev/sdb
yes | sudo mkfs -t ext4 /dev/sdb
sudo mkdir /data1
sudo mount /dev/sdb /data1
sudo sed -i '$ a\\/dev/sdb   /data1       ext4    defaults,nofail  0   2' /etc/fstab
sudo mount -a


# PUT A COPY OF THE JRE INTO THIS TEMP DIR
cd /home/ec2-user/
mkdir temp
cd temp

# INSTALL JAVA 8
sudo rpm -i jre-8u131-linux-x64.rpm
sudo alternatives --install /usr/bin/java java /usr/java/default/bin/java 20000
export JAVA_HOME=/usr/java/default

#CHECK IT IS 1.8
java -version

# INSTALL ELASTICSEARCH
cd /home/ec2-user/
wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-6.1.2.tar.gz
tar zxfv elasticsearch-6.1.2.tar.gz
sudo mkdir /usr/local/elasticsearch
sudo cp -R elasticsearch-6.1.2/* /usr/local/elasticsearch/
rm -fr elasticsearch*


# INSTALL CLOUD PLUGIN
cd /usr/local/elasticsearch/
sudo bin/elasticsearch-plugin install -b discovery-ec2

sudo rm -f /usr/local/elasticsearch/config/elasticsearch.yml
sudo rm -f /usr/local/elasticsearch/config/jvm.options
sudo rm -f /usr/local/elasticsearch/config/log4j2.properties


#INSTALL GIT
sudo yum install -y git-core


#INSTALL PYTHON27
sudo yum -y install python27

#INSTALL SUPERVISOR
sudo yum install -y libffi-devel
sudo yum install -y openssl-devel
sudo yum groupinstall -y "Development tools"

sudo pip install pyopenssl
sudo pip install ndg-httpsclient
sudo pip install pyasn1
sudo pip install requests
sudo pip install supervisor

cd /usr/bin
sudo ln -s /usr/local/bin/supervisorctl supervisorctl


#INSTALL gunicorn
sudo pip install gunicorn

#INSTALL nginx
sudo yum install -y nginx
# IMPORTANT: nginx INSTALL SCREWS UP PERMISSIONS
sudo chown -R ec2-user:ec2-user /var/lib/nginx/

# SIMPLE PLACE FOR LOGS
chown ec2-user:ec2-user -R /data1
mkdir /data1/logs
cd /
ln -s  /data1/logs /home/ec2-user/logs


# CLONE ACTIVEDATA
cd ~
git clone https://github.com/klahnakoski/ActiveData.git

cd ~/ActiveData/
git checkout frontend6
sudo pip install -r requirements.txt


###############################################################################
# PLACE ALL CONFIG FILES
###############################################################################

# ELASTICSEARCH CONFIG
sudo cp ~/ActiveData/resources/config/elasticsearch.yml /usr/local/elasticsearch/config/elasticsearch.yml

# FOR SOME REASON THE export COMMAND DOES NOT SEEM TO WORK
# THIS SCRIPT SETS THE ES_MIN_MEM/ES_MAX_MEM EXPLICITLY
sudo cp ~/ActiveData/resources/config/elasticsearch.in.sh /usr/local/elasticsearch/bin/elasticsearch.in.sh

# SUPERVISOR CONFIG
sudo cp ~/ActiveData/resources/config/supervisord.conf /etc/supervisord.conf



# START DAEMON (OR THROW ERROR IF RUNNING ALREADY)
sudo /usr/local/bin/supervisord -c /etc/supervisord.conf

# READ CONFIG
sudo /usr/local/bin/supervisorctl reread
sudo /usr/local/bin/supervisorctl update


#NGINX CONFIG
sudo cp ~/ActiveData/resources/config/nginx.conf /etc/nginx/nginx.conf

sudo /etc/init.d/nginx start

more /logs/nginx.pid


