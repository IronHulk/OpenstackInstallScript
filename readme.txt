

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