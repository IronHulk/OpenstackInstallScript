
This python script was developed during my internship. The goal was to deploy a complete openstack cloud platform automatically. The script was designed for Openstack Juno using Ubuntu 14.04 LTS. 

Since I no longer work in the company and openstack is still in rapid deployment, for more detailed  and updated information please consult the offical openstack documentation --> http://docs.openstack.org

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
