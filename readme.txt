
This python script was developed when i was doing my intership. It was aimed to setup openstack cloud platform in one go.
The script was designed for Openstack Juno using Ubuntu 14.04 LTS.

<!!!>Warning</!!!>:
Since I don't work with openstack any more, for more detailed  and updated information, please refer to the offical openstack documentation --> http://docs.openstack.org






Notes:
if you encounter "Error: Unauthorized: Unable to get nova services list", Please Try to restart nova services
manually:
1. sudo nova-manage db sync
2. sudo service nova-api restart
3. sudo service nova-cert restart
4. sudo service nova-consoleauth restart
5. sudo service nova-conductor restart
6. sudo service nova-scheduler restart
7. sudo service nova-novncproxy restart

or go to utils folder and execute:

sudo sh nova-service-restart.sh
