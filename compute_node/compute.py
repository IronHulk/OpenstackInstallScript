import shutil
import os, sys
from openstack_node.node import OpenstackNode
from subprocess import call
from utils.tools import c_print

__author__ = 'Fernando'


class ComputeNode(OpenstackNode):
	def __init__(self):
		OpenstackNode.__init__(self)

	def prepare_pkg(self):
		pkg_dir = '/package/compute/'
		if not os.path.isfile(os.path.abspath('.') + pkg_dir):
			if os.path.isfile(os.path.abspath('.') + '/package/compute.zip'):
				c_print('Install zip ...')
				call('apt-get install zip -y', shell=True)
				call('unzip ./package/compute.zip', shell=True)
				shutil.move('./compute', './package/')

				c_print('Getting package ready ...')
				for package in os.listdir('.' + pkg_dir):
					print 'Copying ', package, ' -> ', '/var/cache/apt/archives'
					shutil.copy(os.path.abspath('.') + pkg_dir + package, '/var/cache/apt/archives/')
		else:
			c_print('Packages already extracted, continue next operation ...')

	def install(self):
		self.prepare_pkg()

		self.keyring_setup()

		c_print('Installing the Compute hypervisor component ...')
		call('apt-get install nova-compute sysfsutils -y', shell=True)

		self.config()

		if os.path.isfile('/var/lib/nova/nova.sqlite'): os.remove('/var/lib/nova/nova.sqlite')


	def config(self):
		confirm_ip = False

		while confirm_ip == False:
			controller_ip = raw_input('\033[36m Please type in your controller node ip address: \033[0m')
			choice = raw_input('Controller ip is going to be set as %s\nContinue installation? Y/N/Q: ' % controller_ip)

			if choice.lower() in ('y', 'yes'):
				confirm_ip = True
			elif choice.lower() in ('q', 'quit'):
				sys.exit()

		c_print('Writing configuration files ...')

		if os.path.isfile('/etc/nova/nova.conf.modified') is False:
			config = open('/etc/nova/nova.conf', 'a')
			print >> config, 'rpc_backend = rabbit \nrabbit_host = %s \nrabbit_password = %s' % (controller_ip, 'openstack')
			print >> config, '\nauth_strategy = keystone\n'
			print >> config, 'my_ip = %s' % self.current_ip
			print >> config, 'vnc_enabled = True \nvncserver_listen = 0.0.0.0'
			print >> config, 'vncserver_proxyclient_address = %s \nnovncproxy_base_url = http://%s:6080/vnc_auto.html' \
											 % (self.current_ip, controller_ip)
			print >> config, '\n[keystone_authtoken]\n'
			print >> config, 'auth_uri = http://%s:5000/v2.0 \nidentity_uri = http://%s:35357 ' % (controller_ip, controller_ip)
			print >> config, 'admin_tenant_name = service \nadmin_user = nova \nadmin_password = %s' % 'openstack'

			print >> config, '\n[glance]\n'
			print >> config, 'host = %s' % controller_ip

			config.close()

			print >> open('/etc/nova/nova.conf.modified','w'), 'Modified'

		c_print('Restarting the Compute Service ...')
		call('service nova-compute restart', shell=True)

	def telemetry(self):
		confirm_ip = False
		while not confirm_ip:

			controller_ip = raw_input('\033[36m Please type in your controller node ip address: \033[0m')
			choice = raw_input('Controller ip is going to be set as %s\nContinue installation? Y/N/Q: ' % controller_ip)

			if choice.lower() in ('y', 'yes'):
				confirm_ip = True
			elif choice.lower() in ('q', 'quit'):
				sys.exit()

		self.chusr_sudo()
		c_print('Install Telemetry packages ...')
		call('apt-get install ceilometer-agent-compute -y', shell=True)


		modified_content = ''
		for line in open('/etc/nova/nova.conf'):
			if line == '[DEFAULT]\n':
				line += 'instance_usage_audit = True\n' + \
								'instance_usage_audit_period = hour\n' + \
								'notify_on_state_change = vm_and_task_state\n' + \
								'notification_driver = nova.openstack.common.notifier.rpc_notifier\n' + \
								'notification_driver = ceilometer.compute.nova_notifier\n'
			modified_content += line

		print >> open('/etc/nova/nova.conf','w'), modified_content

		c_print('Restarting the Compue service ...')
		call('service nova-compute restart', shell=True)


		c_print('Editing ceilometer.conf ...')
		modified_content = ''
		for line in open('/etc/ceilometer/ceilometer.conf'):
			if line == '[publisher]\n':
				line += 'metering_secret = %s\n' % 'ceilometer'
			elif line == '[DEFAULT]\n':
				line += 'rabbit_host = %s\nrabbit_password = %s\n' % (controller_ip, 'openstack')
			elif 'keystone_authtoken' in line:
				line += 'auth_uri = http://%s:5000/v2.0 \n' % controller_ip + \
				'identity_uri = http://%s:35357 \n' % controller_ip + \
				'admin_tenant_name = service \n' + \
				'admin_user = ceilometer \n' + \
				'admin_password = %s\n' % 'openstack'
			elif 'service_credentials' in line:
				line += 'os_auth_url = http://%s:5000/v2.0 \n' % controller_ip + \
				        'os_username = ceilometer\n' + \
								'os_tenant_name = service\n' + \
								'os_password = %s\n' % 'openstack' + \
								'os_endpoint_type = internalURL\n'
			modified_content += line

		print >> open('/etc/ceilometer/ceilometer.conf', 'w'), modified_content

		c_print('Restarting the service with its new settings ...')
		call('service ceilometer-agent-compute restart', shell=True)


	# Configure neutron settings on compute node
	def neutron(self):
		confirm_ip = False
		controller_ip = ''
		while not confirm_ip:
			controller_ip = raw_input('\033[0mPlease type in the controller ip: \033[0m')
			choice = raw_input('You just typed controller_ip = %s, do you want continue? Y/N/Q ' % controller_ip)
			if choice.lower() in ('y', 'yes'): confirm_ip = True
			elif choice.lower() in ('q', 'quit'):
				c_print('Quitting installation process')
				sys.exit()

		self.chusr_sudo()
		c_print('Configuring neutron settings on compute node ...')
		c_print('Editing /etc/sysctl.conf file ...')
		print >> open('/etc/sysctl.conf', 'a'), 'net.ipv4.conf.all.rp_filter=0\nnet.ipv4.conf.default.rp_filter=0\n'

		c_print('Implementing the changes ...')
		call('sysctl -p', shell=True)

		c_print('Installing the Networking components ...')
		call('apt-get install neutron-plugin-ml2 neutron-plugin-openvswitch-agent -y', shell=True)

		c_print('Configuring the Networking common components ...')
		c_print('Editing the /etc/neutron/neutron.conf file ...')

		if not os.path.isfile('/etc/neutron/neutron.conf.modified'):
			modified_content = ''
			for line in open('/etc/neutron/neutron.conf'):
				if line == '[DEFAULT]\n':
					line += 'rpc_backend = rabbit\nrabbit_host = %s\n' % controller_ip + \
									'rabbit_password = %s\n' % 'openstack' + 'auth_strategy = keystone\n' + \
									'core_plugin = ml2\nservice_plugins = router\nallow_overlapping_ips = True\n'
				elif 'connection' in line and 'sqlite' in line: line = ''
				elif 'auth_host' in line:
					line = 'auth_uri = http://%s:5000/v2.0\n' % controller_ip
				elif 'auth_port' in line:
					line = 'identity_uri = http://%s:35357\n' % controller_ip
				elif 'auth_protocol' in line:
					line = ''
				elif 'admin_tenant_name' in line and '%SERVICE_TENANT_NAME%' in line:
					line = 'admin_tenant_name = service\n'
				elif 'admin_user' in line and '%SERVICE_USER%' in line:
					line = 'admin_user = neutron\n'
				elif 'admin_password' in line and '%SERVICE_PASSWORD%' in line:
					line = 'admin_password = %s\n' % 'openstack'

				modified_content += line

			print >> open('/etc/neutron/neutron.conf', 'w'), modified_content
			print >> open('/etc/neutron/neutron.conf.modified', 'w'), 'Modified'

		c_print('Configure the Modular Layer 2 (ML2) plug-in ...')
		c_print('Editing the /etc/neutron/plugins/ml2/ml2_conf.ini file ...')

		tunnel_ip = raw_input('Please type in the ip address used by tunnel interface ...')
		modified_content = ''
		for line in open('/etc/neutron/plugins/ml2/ml2_conf.ini'):
			if line == '[ml2]\n':
				line += 'type_drivers = flat,gre\ntenant_network_types = gre\nmechanism_drivers = openvswitch\n'
			elif line == '[ml2_type_gre]\n':
				line += 'tunnel_id_ranges = 1:1000\n'
			elif line == '[securitygroup]\n':
				line += '' + 'enable_security_group = True\nenable_ipset = True\n' + \
					'firewall_driver = neutron.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver\n'
			modified_content += line

		print >> open('/etc/neutron/plugins/ml2/ml2_conf.ini', 'w'), modified_content
		print >> open('/etc/neutron/plugins/ml2/ml2_conf.ini', 'a'), '[ovs]\n' + \
			'local_ip = %s\nenable_tunneling = True\n'  % tunnel_ip + \
			'[agent]\n' + 'tunnel_types = gre\n'

		c_print('Configure the Open vSwitch (OVS) service ...')
		call('service openvswitch-switch restart', shell=True)

		modified_content = ''
		for line in open('/etc/nova/nova.conf'):
			if line == '[DEFAULT]\n':
				line += 'network_api_class = nova.network.neutronv2.api.API\n' + \
					'security_group_api = neutron\n' + \
					'linuxnet_interface_driver = nova.network.linux_net.LinuxOVSInterfaceDriver\n' +\
					'firewall_driver = nova.virt.firewall.NoopFirewallDriver\n'
			modified_content += line

		print >> open('/etc/nova/nova.conf', 'w'), modified_content
		print >> open('/etc/nova/nova.conf', 'a'), '[neutron]\n' + 'url = http://%s:9696\n' % controller_ip + \
			'auth_strategy = keystone\n' + \
			'admin_auth_url = http://%s:35357/v2.0 \nadmin_tenant_name = service\n'  % controller_ip + \
			'admin_username = neutron\nadmin_password = %s\n' % 'openstack'

		c_print('Restarting the Compute service ...')
		call('service nova-compute restart', shell=True)
		c_print('Restarting the Open vSwitch (OVS) agent ...')
		call('service neutron-plugin-openvswitch-agent restart', shell=True)

