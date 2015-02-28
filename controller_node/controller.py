import os, sys, time, shutil
from openstack_node.node import OpenstackNode
from utils.tools import c_print, e_print
from subprocess import call, CalledProcessError

__author__ = 'Fernando Zhu'

class ControllerNode(OpenstackNode):

	component_list = {'1': 'keystone', '2': 'glance', '3': 'compute', '4': 'dashboard'}

	def __init__(self):
		OpenstackNode.__init__(self)


	def install(self):
		confirm_install = False
		while confirm_install == False:
			c_print('''
The following components will be installed automatically:
1. keystone
2. glance
3. compute
4. dashboard

There are two types of network available, select the one you prefer:
1. nova-network
2. neutron-network

			''')
			network_choice = raw_input('please choose option 1 or 2: ')

			if network_choice == '1':
				self.component_list[str(len(self.component_list) + 1)] = 'nova-network'
			elif network_choice == '2':
				self.component_list[str(len(self.component_list) + 1)] = 'neutron-network'
			else:
				e_print('Invalid option')
				continue

			c_print("You've selected : ")
			for (key, value) in sorted(self.component_list.items()): c_print(key+': '+ value)

			install_choice = raw_input('Are you sure to install? Y/N/Q: ')
			if install_choice.lower() in ('y', 'yes'): confirm_install = True
			elif install_choice.lower() in ('q', 'quit'): sys.exit()
			else: self.component_list.pop(str(len(self.component_list)))

		c_print('Starting installation...')

		self.prepare_pkg()
		# Compulsory components
		self.keyring_setup()
		self.basic_environ()
		self.keystone()
		self.glance()
		self.compute()
		self.dashboard_setup()

		# Select one from the two
		if self.component_list.get('5') == 'nova-network': self.nova_network()
		elif self.component_list.get('5') == 'neutron-network': self.neutron_network()

	def basic_environ(self):

		c_print('Installing mysql server...')
		call('apt-get install mariadb-server python-mysqldb -y', shell=True)

		if os.path.isfile('/etc/mysql/modified.txt') is False:
			c_print('Configuring /etc/mysql/my.cnf...')
			modified_content = ''
			for line in open('/etc/mysql/my.cnf'):
				if 'bind-address' in line:
					line = 'bind-address = ' + self.current_ip + '\n'
				elif '[mysqld]' == line:
					line += 'default-storage-engine = innodb\n' + \
									'innodb_file_per_table\n' + \
									'collation-server = utf8_general_ci\n' + \
									"init-connect = 'SET NAMES utf8'\n" + \
									'character-set-server = utf8\n'
				modified_content += line

			config = open('/etc/mysql/my.cnf', 'w')
			config.write(modified_content)
			config.close()
			print >> open('/etc/mysql/modified.txt', 'w'), 'modified'

		c_print('Restarting mysql...')
		call('service mysql restart', shell=True)
		c_print('Secure the database service...')
		# call('mysql_secure_installation',shell=True)

		c_print('Installing RabbitMQ message broker service...')
		call('apt-get install rabbitmq-server -y', shell=True)
		c_print('Configuring the message broker service...')
		call('rabbitmqctl change_password guest openstack', shell=True)

	def keystone(self):
		c_print('Adding identity service...')
		c_print('Creating keystone database...')

		self.db_create('keystone')

		c_print('Installing keystone components...')
		call('apt-get install keystone python-keystoneclient -y', shell=True)

		if os.path.isfile('/etc/keystone/keystone.conf.modified') is False:
			c_print('Configuring keystone.conf...')
			config = open('/etc/keystone/keystone.conf', 'r')
			content = config.readlines()
			config.close()
			modified_content = ''
			for line in content:
				if line == '[DEFAULT]\n':
					line += 'admin_token = admin\n' + \
									'verbose = True\n'
				elif 'connection' in line and 'sqlite' in line:
					line = 'connection = mysql://keystone:openstack@' + self.current_ip + '/keystone'
				elif line == '[token]\n':
					line += 'provider = keystone.token.providers.uuid.Provider\n' + \
									'driver = keystone.token.persistence.backends.sql.Token\n'

				modified_content += line
			config = open('/etc/keystone/keystone.conf', 'w')
			config.write(modified_content)
			config.close()
			print >> open('/etc/keystone/keystone.conf.modified', 'w'), 'modified'

		c_print('Populating the identity service database...')
		call('keystone-manage db_sync', shell=True)
		c_print('Restarting the Identity service...')
		call('service keystone restart', shell=True)
		time.sleep(5)
		if os.path.isfile('/var/lib/keystone/keystone.db'): os.remove('/var/lib/keystone/keystone.db')
		call("(crontab -l -u keystone 2>&1 | grep -q token_flush) || \
					echo '@hourly /usr/bin/keystone-manage token_flush >/var/log/keystone/keystone-tokenflush.log \
					2>&1' >> /var/spool/cron/crontabs/keystone", shell=True)

		##### Create tenants, users and roles #####

		c_print('Dropping superuser privilege...')
		c_print('Switching back to user %s with uid %s...\033[0m' % (os.environ['SUDO_USER'], os.environ['SUDO_UID']))
		os.seteuid(int(os.environ['SUDO_UID']))

		os.environ['OS_SERVICE_TOKEN'] = 'admin'
		os.environ['OS_SERVICE_ENDPOINT'] = 'http://' + self.current_ip +  ':35357/v2.0'


		try:
			##### Admin #####
			c_print('Creating the admin tenant...')
			call('keystone tenant-create --name admin --description "Admin Tenant"', shell=True)

			c_print('Creating the admin user...')
			call('keystone user-create --name admin --pass openstack --email admin@localhost', shell=True)

			c_print('Creating the admin role...')
			call('keystone role-create --name admin', shell=True)

			c_print('Adding the tenant and user to the admin role...')
			call('keystone user-role-add --tenant admin --user admin --role admin', shell=True)

			c_print('Creating the _member_ role:')
			call('keystone role-create --name _member_', shell=True)

			c_print('Adding the admin tenant and user to the _member_ role...')
			call('keystone user-role-add --tenant admin --user admin --role _member_', shell=True)

			##### Demo #####
			c_print('Creating the demo tennat...')
			call('keystone tenant-create --name demo --description "Demo Tenant"', shell=True)
			c_print('Creating the demo user...')
			call('keystone user-create --name demo --pass openstack --email demo@localhost', shell=True)
			c_print('Adding the demo tenant and user to the _member_ role...')
			call('keystone user-role-add --tenant demo --user demo --role _member_', shell=True)

			c_print('Creating the service tenant...')
			call('keystone tenant-create --name service --description "Service Tenant"', shell=True)

			c_print('Creating service entity for the identity service...')
			call('keystone service-create --name keystone --type identity --description "Openstack Identity"', shell=True)

			c_print('Creating the API endpoint for the Identity service..')
			call('keystone endpoint-create ' +
					 "--service-id $(keystone service-list | awk ' / identity / {print $2}') " + \
					 '--publicurl http://' + self.current_ip + ':5000/v2.0 ' + \
					 '--internalurl http://' + self.current_ip + ':5000/v2.0 ' + \
					 '--adminurl http://' + self.current_ip + ':35357/v2.0 ' + \
					 '--region regionOne', shell=True)


		except CalledProcessError:
			e_print('Process error, please check')
			sys.exit()
			#########################################
		c_print('Deleting environ varialbes...')
		del os.environ['OS_SERVICE_TOKEN']
		del os.environ['OS_SERVICE_ENDPOINT']

		c_print('Veritying operation...')
		c_print('As the admin tenant and user, request an authentication token:')
		call('keystone --os-tenant-name admin --os-username admin --os-password openstack ' +
				 '--os-auth-url http://' + self.current_ip + ':35357/v2.0 token-get', shell=True)

		c_print('As the admin tenant and user, list tenants to verify that the admin tenant and user')
		c_print('can execute admin-only CLI commands and that the Identity service contains the tenants')
		c_print('that created before')
		call('keystone --os-tenant-name admin --os-username admin --os-password openstack ' +
				 '--os-auth-url http://' + self.current_ip + ':35357/v2.0 tenant-list', shell=True)

		c_print('As the admin tenant and user, list user to verify that the Identity service contains the')
		c_print('users that you created before')
		call('keystone --os-tenant-name admin --os-username admin --os-password openstack ' +
				 '--os-auth-url http://' + self.current_ip + ':35357/v2.0 user-list', shell=True)

		c_print('As the admin tenant and user, list roles to verify that the identity service contains the')
		c_print('users that created before...')
		call('keystone --os-tenant-name admin --os-username admin --os-password openstack ' +
				 '--os-auth-url http://' + self.current_ip + ':35357/v2.0 role-list', shell=True)

		c_print('As the demo tenant and user, request an authentication token:')
		call('keystone --os-tenant-name demo --os-username demo --os-password openstack ' +
				 '--os-auth-url http://' + self.current_ip + ':35357/v2.0 token-get', shell=True)

	def glance(self):
		c_print('Install and configure Glance')
		c_print('Creating glance database...')

		self.db_create('glance')

		c_print('Loading client environment varialbes...')
		self.add_admin_env(self.current_ip)

		c_print('Creating glance user...')
		call('keystone user-create --name glance --pass openstack', shell=True)
		c_print('Linking the glance user to the service tenant and admin role...')
		call('keystone user-role-add --user glance --tenant service --role admin', shell=True)
		c_print('Creating the glance service...')
		call('keystone service-create --name glance --type image --description "Openstack Image Service"', shell=True)
		c_print('Creating the identity service endpoints...')
		call('keystone endpoint-create ' +
				 "--service-id $(keystone service-list | awk '/ image / {print $2}') " +
				 '--publicurl http://' + self.current_ip + ':9292 ' +
				 '--internalurl http://' + self.current_ip + ':9292 ' +
				 '--adminurl http://' + self.current_ip + ':9292 ' +
				 '--region regionOne', shell=True)

		c_print('#' * 8 + 'Install and configure the Image Service components' + '#' * 8)
		c_print('Getting back the superuser privilege...')
		os.seteuid(0)
		call('apt-get install glance python-glanceclient -y', shell=True)

		modified_content = ''
		c_print('Configuring /etc/glance/glance-api.conf')
		for line in open('/etc/glance/glance-api.conf'):
			if 'sqlite_db' in line and 'glance' in line:
				line = 'connection = mysql://glance:openstack@' + self.current_ip + '/glance'
			elif line == '[keystone_authtoken]\n':
				line += 'auth_uri = http://' + self.current_ip + ':5000/v2.0\n'
			elif 'identity_uri' in line:
				line = 'identity_uri = http://' + self.current_ip + ':35357\n'
			elif 'admin_tenant_name' in line and 'SERVICE' in line:
				line = 'admin_tenant_name = service\n'
			elif 'admin_user' in line and 'SERVICE' in line:
				line = 'admin_user = glance\n'
			elif 'admin_password' in line and 'SERVICE' in line:
				line = 'admin_password = openstack\n'
			elif line == '[paste_deploy]\n':
				line += 'flavor = keystone\n'
			elif line == '[glance_store]\n':
				line += 'default_store = file\n'
			elif line == '[DEFAULT]\n':
				line += 'verbose = True\n'
			modified_content += line
		print >> open('/etc/glance/glance-api.conf', 'w'), modified_content

		modified_content = ''
		c_print('Editing /etc/glance/glance-registry.conf')
		if os.path.isfile('/etc/glance/glance-registry.conf.modified') is False:
			for line in open('/etc/glance/glance-registry.conf'):
				if 'sqlite_db' in line and 'glance' in line:
					line = 'connection = mysql://glance:openstack@' + self.current_ip + '/glance'
				elif line == '[keystone_authtoken]\n':
					line += 'auth_uri = http://' + self.current_ip + ':5000/v2.0\n'
				elif 'identity_uri' in line:
					line = 'identity_uri = http://' + self.current_ip + ':35357\n'
				elif 'admin_tenant_name' in line and 'SERVICE' in line:
					line = 'admin_tenant_name = service\n'
				elif 'admin_user' in line and 'SERVICE' in line:
					line = 'admin_user = glance\n'
				elif 'admin_password' in line and 'SERVICE' in line:
					line = 'admin_password = openstack\n'
				elif line == '[paste_deploy]\n':
					line += 'flavor = keystone\n'
				modified_content += line
			print >> open('/etc/glance/glance-registry.conf', 'w'), modified_content
		print >> open('/etc/glance/glance-registry.conf.modified', 'w'), 'modified'

		c_print('Pupulating the Image Service database...')
		call('glance-manage db_sync', shell=True)
		c_print('Restarting Image Service...')
		call('service glance-registry restart', shell=True)
		call('service glance-api restart', shell=True)
		if os.path.isfile('/var/lib/glance/glance.sqlite'): os.remove('/var/lib/glance/glance.sqlite')

		c_print('Verity operation')
		c_print('Dropping of root privilege...')
		os.seteuid(int(os.environ['SUDO_UID']))

		if os.path.isdir('images') is False: os.makedirs('images')
		os.chdir('images')
		c_print('Downloading image...')
		call('wget http://192.168.50.80:33819/huangshi/cirros-0.3.3-x86_64-disk.img', shell=True)

		c_print('Adding environment variables...')
		self.add_admin_env(self.current_ip)
		c_print('Uploading the image to the Image Service...')
		call('glance image-create --name "cirros-0.3.3-x86_64" --file cirros-0.3.3-x86_64-disk.img ' + \
				 '--disk-format qcow2 --container-format bare --is-public True --progress', shell=True)
		c_print('Confirming upload of the image and validate attributes:')
		call('glance image-list', shell=True)

	def compute(self):
		c_print('#' * 8 + 'Setting up nova...' + '#' * 8)
		c_print('Creating nova database...')

		self.db_create('nova')

		c_print('Adding admin environment variables..')
		self.add_admin_env(self.current_ip)

		c_print('Creating the nova user...')
		call('keystone user-create --name nova --pass openstack', shell=True)

		c_print('Linking the nova user to the service tenant and amdin role...')
		call('keystone user-role-add --user nova --tenant service --role admin', shell=True)

		c_print('Creating the nova service...')
		call('keystone service-create --name nova --type compute --description "Openstack Compute"', shell=True)

		c_print('Creating the Compute Service endpoints...')
		call('keystone endpoint-create ' +
		     "--service-id $(keystone service-list | awk '/ compute / {print $2}') " +
		     '--publicurl http://' + self.current_ip + ':8774/v2/%\(tenant_id\)s ' +
		     '--internalurl http://' + self.current_ip + ':8774/v2/%\(tenant_id\)s ' +
		     '--adminurl http://' + self.current_ip + ':8774/v2/%\(tenant_id\)s ' +
		     '--region regionOne', shell=True)

		c_print('Installing Compute controller components...')
		c_print('Getting permission back...')
		os.seteuid(0)

		call('apt-get install nova-api nova-cert nova-conductor nova-consoleauth ' +
				 'nova-novncproxy nova-scheduler python-novaclient -y', shell=True)

		c_print('Configuring /etc/nova/nova.conf...')
		config = open('/etc/nova/nova.conf', 'a')
		print >> config, '\nrpc_backend = rabbit'
		print >> config, 'rabbit_host = ' + self.current_ip
		print >> config, 'rabbit_password = openstack'
		print >> config, 'auth_strategy = keystone'
		print >> config, 'my_ip = ' + self.current_ip
		print >> config, 'vncserver_listen = ' + self.current_ip
		print >> config, 'vncserver_proxyclient_address = ' + self.current_ip
		print >> config, 'verbose = True'
		print >> config, '\n[database]'
		print >> config, 'connection = mysql://nova:openstack@' + self.current_ip + '/nova'
		print >> config, '\n[keystone_authtoken]'
		print >> config, 'auth_uri = http://' + self.current_ip + ':5000/v2.0\n' + \
										 'identity_uri = http://' + self.current_ip + ':35357\n' + \
										 'admin_tenant_name = service\n' + \
										 'admin_user = nova\n' + \
										 'admin_password = openstack\n'
		print >> config, '\n[glance]\n' + \
		                 'host = ' + self.current_ip

		c_print('Populating the Copute database...')
		'''
		call('nova-manage db sync ', shell=True); time.sleep(15)

		c_print('Restarting the Compute services...')
		call('service nova-api restart', shell=True); time.sleep(5)
		call('service nova-cert restart', shell=True); time.sleep(5)
		call('service nova-consoleauth restart', shell=True); time.sleep(5)
		call('service nova-scheduler restart', shell=True); time.sleep(5)
		call('service nova-conductor restart', shell=True); time.sleep(5)
		call('service nova-novncproxy restart', shell=True); time.sleep(5)
		'''
		call('nova-manage db sync && service nova-api restart && service nova-cert restart && service nova-consoleauth ' +
		     'restart && service nova-scheduler restart && service nova-conductor restart && service nova-novncproxy ' +
		     'restart', shell=True); time.sleep(5)

		if os.path.isdir('/var/lib/nova/nova.sqlite'): os.remove('/var/lib/nova/nova.sqlite')

	def prepare_pkg(self):

		pkg_dir = '/package/controller/'

		if not os.path.isfile(os.path.abspath('.') + pkg_dir):
			if os.path.isfile(os.path.abspath('.') + '/package/controller.zip'):
				c_print('Install zip ...')
				call('apt-get install zip -y', shell=True)
				call('unzip ./package/controller.zip', shell=True)
				shutil.move('./controller', './package/')

				c_print('Getting package ready ...')
				for package in os.listdir('.' + pkg_dir):
					print 'Copying ', package,  ' -> ', '/var/cache/apt/archives'
					shutil.copy(os.path.abspath('.') + pkg_dir + package, '/var/cache/apt/archives/')
		else:
			c_print('Packages already extracted, continue next operation ...')

	def dashboard_setup(self):
		c_print('Installing dashboard components')
		call('apt-get install openstack-dashboard apache2 libapache2-mod-wsgi '+
				'memcached python-memcache -y',shell=True)

		modified_content = ''
		for line in open('/etc/openstack-dashboard/local_settings.py'):
			if 'OPENSTACK_HOST' in line and '127' in line:
				line = "OPENSTACK_HOST = '"+ self.current_ip +"'\n"
			elif line == "ALLOWED_HOSTS = '*'\n":
				line = "ALLOWED_HOSTS = ['*']\n"
			elif 'TIME_ZONE' in line:
				line = "TIME_ZONE = 'Asia/Shanghai'\n"
			modified_content += line

		print >> open('/etc/openstack-dashboard/local_settings.py','w'), modified_content

		c_print('Removing ubuntu theme...')
		call('apt-get remove --purge openstack-dashboard-ubuntu-theme -y',shell=True)

		c_print('Restarting the web server and session storage service...')
		call('service apache2 restart',shell=True)
		call('service memcached restart',shell=True)

	def nova_network(self):
		self.chusr_sudo()
		c_print('Configuring the lagecy networking on Controller Node ...')

		if os.path.isfile('/etc/nova/nova.conf.nova-network') is False:
			modified_content = ''
			for line in open('/etc/nova/nova.conf'):
				if line == '[DEFAULT]\n':
					line = '\n[DEFAULT]\nnetwork_api_class = nova.network.api.API\nsecurity_group_api = nova\n'

				modified_content += line
			print >> open('/etc/nova/nova.conf', 'w'), modified_content
			print >> open('/etc/nova/nova.conf.nova-network', 'w'), 'Modified'

		c_print('Restarting Compute Service ...')
		call('service nova-api restart', shell=True)
		call('service nova-scheduler restart', shell=True)
		call('service nova-conductor restart', shell=True)

	def neutron_network(self):
		c_print('Creating neutron database...')
		self.db_create('neutron')

		self.chusr_normal()

		c_print('Adding environment variables...')
		##### need controller ip arg here
		self.add_admin_env(self.current_ip)

		try:
			c_print('Creating neutron user...')
			call('keystone user-create --name neutron --pass openstack', shell=True)

			c_print('Linking the neutron user to the service tenant and admin role...')
			call('keystone user-role-add --user neutron --tenant service --role admin', shell=True)

			c_print('Creating the neutron service..')
			call('keystone service-create --name neutron --type network --description "Openstack Networking"', shell=True)

			c_print('Creating the Identity service endpoint...')
			call("keystone endpoint-create --service-id $(keystone service-list | awk '/ network / {print $2}') " + \
					 '--publicurl http://' + self.current_ip + ':9696 ' + \
					 '--adminurl http://' + self.current_ip + ':9696 ' + \
					 '--internalurl http://' + self.current_ip + ':9696 ' + \
					 '--region regionOne', shell=True)

		except  CalledProcessError:
			e_print('Error occurred when setting up neutron keystone')

		self.add_admin_env(self.current_ip)

		self.del_env()

		self.chusr_sudo()

		c_print('Installing the Networking components...')
		call('apt-get install neutron-server neutron-plugin-ml2 python-neutronclient -y', shell=True)

		c_print('Configuring the Networking server components...')
		c_print('Editing the /etc/neutron/neutron.conf ...')

		service_id = ''
		# TEMP MARK
		service_id = raw_input('\033[36mPlease type in the service tenant id: \033[0m')
		sys.exit()
		modified_content = ''

		for line in open('/etc/neutron/neutron.conf'):
			if 'connection' in line and 'sqlite' in line:
				line = 'connection = mysql://neutron:%s@%s/neutron' % ('openstack', self.current_ip)
				pass
			elif line == '[DEFAULT]\n':
				line += 'rpc_backend = rabbit \n' + \
				        'rabbit_host = %s \nrabbit_password = %s \n '% (self.current_ip, 'openstack') + \
				        'auth_strategy = keystone\n' + 'core_plugin = ml2\n' + \
								'service_plugins = router\n' + \
								'allow_overlapping_ips = True\n' +\
								'notify_nova_on_port_status_changes = True \nnotify_nova_on_port_data_changes = True\n' + \
								'nova_url = http://%s:8774/v2 \n' % self.current_ip + \
								'nova_admin_auth_url = http://%s:35357/v2.0 \n' % self.current_ip + \
								'nova_region_name = regionOne\n' + \
								'nova_admin_username = nova\n' + \
								'nova_admin_tenant_id = %s\nnova_admin_password = %s\n' % (service_id, 'openstack')

			else:
				pass

			modified_content += line
		print >> open(modified_content, 'w'), modified_content

		c_print('Configuring the Modular Layer (ML2) plug-in ...')

		modified_content = ''
		for line in open('/etc/neutron/plugins/ml2/ml2_conf.ini'):
			if line == '[ml2]\n':
				line += 'type_drivers = flat,gre\n' + \
					'tenant_network_types = gre\n' + \
					'mechanism_drivers = openvswitch\n'
			elif line == '[ml2_type_gre]\n':
				line  += 'tunnel_id_ranges = 1:1000\n'
			elif line == '[securitygroup]\n':
				line += 'enable_security_group = True\n' + \
								'enable_ipset = True\n' + \
								'firewall_driver = neutron.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver\n'
			modified_content += line

		print >> open('/etc/neutron/plugins/ml2/ml2_conf.ini','w'), modified_content

		# INSTALL FINISH TMP POINT
		sys.exit()



		modified_content = ''
		for line in open('/etc/nova/nova.conf'):
			if line == '[DEFAULT]\n':
				line += 'network_api_class = nova.network.neutronv2.api.API\n' + \
								'security_group_api = neutron\n' + \
								'linuxnet_interface_driver = nova.network.linux_net.LinuxOVSInterfaceDriver\n' + \
								'firewall_driver = nova.virt.firewall.NoopFirewallDriver\n'

			modified_content += line

		print >> open('/etc/nova/nova.conf', 'w'), modified_content


		c_print('Populating the database ...')
		call('neutron-db-manage --config-file /etc/neutron/neutron.conf --config-file ' + \
		     '/etc/neutron/plugins/ml2/ml2_conf.ini upgrade juno', shell=True)

		c_print('Restarting the Compute services ...')
		call('service nova-api restart', shell=True)
		call('service nova-scheduler restart', shell=True)
		call('service nova-conductor restart', shell=True)
		call('service neutron-server restart', shell=True)


		# After finishing config neutron node

		print >> open('/etc/nova/nova.conf', 'a'), '[neutron]\n' + \
			'service_metadata_proxy = True \nmetadata_proxy_shared_secret = %s\n' % 'neutron' # METADATA_SECRET
		c_print('Restaring Compute API service ...')
		call('service nova-api restart', shell=True)


	def telemetry(self):
		c_print('Installing MongoDB ...')
		self.chusr_sudo()
		call('apt-get install mongodb-server -y', shell=True)

		modified_content = ''
		for line in open('/etc/mongodb.conf'):
			if 'bind_ip' in line: line = 'bind_ip = %s \n' % self.current_ip
			modified_content += line
		print >> open('/etc/mongodb.conf', 'w'), modified_content

		c_print('Restarting MongoDB service')
		call('service mongodb restart', shell=True)

		c_print('Creating the ceilometer database ...')
		call("mongo --host %s --eval 'db = db.getSiblingDB(" % self.current_ip + '"ceilometer");'  + \
		     ' db.addUser({user: ' + '"ceilometer",' + \
		     'pwd: "openstack",' + 'roles: [ "readWrite", "dbAdmin" ]})' + "'", shell=True)

		self.add_admin_env(self.current_ip)

		self.chusr_normal()

		c_print('Creating the ceilometer user ...')
		call('keystone user-create --name ceilometer --pass openstack', shell=True)
		c_print('Linking the ceilometer user to the service tenant and admin role ...')
		call('keystone user-role-add --user ceilometer --tenant service --role admin', shell=True)
		c_print('Creating the ceilometer service ...')
		call('keystone service-create --name ceilometer --type metering --description "Telemetry"', shell=True)
		c_print('Creating the identity service endpoints ...')
		call('keystone endpoint-create --service-id $(' + \
		     "keystone service-list | awk '/ metering / {print $2}') " + \
		     "--publicurl http://%s:8777 "  % self.current_ip + \
		     '--internalurl http://%s:8777 --adminurl ' % self.current_ip + \
		     'http://%s:8777 --region regionOne' % self.current_ip, shell=True)


		c_print('Install and configuring the Telemetry module components ...')
		self.del_env()
		self.chusr_sudo()
		call('apt-get install ceilometer-api ceilometer-collector ceilometer-agent-central ' + \
			'ceilometer-agent-notification ceilometer-alarm-evaluator ceilometer-alarm-notifier ' + \
			'python-ceilometerclient -y', shell=True)

		c_print('Editing /etc/ceilometer/ceilometer.conf file ...')
		modified_content = ''
		for line in open('/etc/ceilometer/ceilometer.conf'):
			if 'connection' in line and 'sqlite' in line:
				line = 'connection = mongodb://ceilometer:%s@%s:27017/ceilometer' % ('openstack', self.current_ip)
			elif line == '[DEFAULT]\n':
				line += 'rpc_backend = rabbit \nrabbit_host = %s \nrabbit_password = %s\n' % (self.current_ip, 'openstack') + \
					'auth_strategy = keystone\n'
			elif 'keystone_authtoken' in line:
				line += 'auth_uri = http://%s:5000/v2.0\n' % self.current_ip + \
				        'identity_uri = http://%s:35357\n' % self.current_ip + \
				        'admin_tenant_name = service \n' + \
				        'admin_user = ceilometer \nadmin_password = %s\n' % 'openstack'
			elif 'service_credentials' in line:
				line += 'os_auth_url = http://%s:5000/v2.0 \nos_username = ceilometer\n' % self.current_ip + \
					'os_tenant_name = service\n' + \
					'os_password = %s\n' % 'openstack'
			elif line == '[publisher]\n':
				line += 'metering_secret = %s\n' % 'ceilometer'

			modified_content += line

		print >> open('/etc/ceilometer/ceilometer.conf', 'w'), modified_content

		c_print('Installing Additional packages (without these packages ceilometer-api would not start properly...')
		call('apt-get install python-pymongo python-bson -y', shell=True)

		c_print('Restarting the Telemetry services ...')
		call('service ceilometer-agent-central restart', shell=True)
		call('service ceilometer-agent-notification restart', shell=True)
		call('service ceilometer-api restart', shell=True)
		call('service ceilometer-collector restart', shell=True)
		call('service ceilometer-alarm-evaluator restart', shell=True)
		call('service ceilometer-alarm-notifier restart', shell=True)

