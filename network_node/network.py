import os, sys
from utils.tools import c_print, e_print
from openstack_node.node import OpenstackNode
from subprocess import call

__author__ = 'Fernando Zhu'


class NovaNetwork(OpenstackNode):
	def __init__(self):
		OpenstackNode.__init__(self)

	def install(self):
		self.chusr_sudo()
		c_print('Installing the legacy networking components')
		call('apt-get install nova-network nova-api-metadata -y', shell=True)

		self.config()

		c_print('Restart the services ...')
		call('service nova-network restart', shell=True)
		call('service nova-api-metadata restart', shell=True)

		while not confirm_reboot:
			choice = raw_input('\033[36mYou need to reboot to activate the above changes, reboot now? Y/N\033[0m')
			if choice.lower() in ('yes', 'y'): confirm_reboot = True
			elif choice.lower() in ('no', 'n'): sys.exit()

		call('reboot', shell=True)


	def config(self):
		c_print('Configuring the legacy networking ...')

		flat_interface = raw_input('Please type the flat interface name: ')
		public_interface = raw_input('Please type the public interface name: ')

		c_print('Configuring network interface ...')

		config = open('/etc/network/interfaces','a')
		print >> config, 'auto %s' % public_interface
		print >> 'iface %s inet manual' % public_interface
		print >> '/tup ip link set dev $IFACE up'
		print >> '/tup down link set dev $IFACE down'
		config.close()



		if not os.path.isfile('/etc/nova/nova.conf.nova-network'):
			modified_content = ''
			for line in open('/etc/nova/nova.conf'):
				if line == '[DEFAULT]\n':
					line += 'network_api_class = nova.network.api.API\n' + 'security_group_api = nova\n' +\
					'firewall_driver = nova.virt.libvirt.firewall.IptablesFirewallDriver\n' + \
					'network_manager = nova.network.manager.FlatDHCPManager\n' + \
					'network_size = 254\n' + \
					'allow_same_net_traffic = False \n' + \
					'multi_host = True\n' + \
					'send_arp_for_ha = True \n' + \
					'share_dhcp_address = True \n' + \
					'force_dhcp_release = True \n' + \
					'flat_network_bridge = br100 \n' + \
					'flat_interface = %s \n' % flat_interface + \
					'public_interface = %s \n' % public_interface
				modified_content += line

			print >> open('/etc/nova/nova.conf', 'w'), modified_content
			print >> open('/etc/nova/nova.conf.nova-network','w'), 'Modified'

class NeutronNetwork(OpenstackNode):
	def __init__(self):
		OpenstackNode.__init__(self)

	def install(self):

		controller_ip  = raw_input('Please type in the controller the ip address: ')

		self.chusr_sudo()

		self.keyring_setup()

		c_print('Editing the /etc/sysctl.conf file ...')
		config = open('/etc/sysctl.conf', 'a')
		print >> config, '\nnet.ipv4.ip_forward=1\nnet.ipv4.conf.all.rp_filter=0\nnet.ipv4.conf.default.rp_filter=0\n'
		config.close()

		c_print('Implement the changes ...')
		call('sysctl -p', shell=True)

		c_print('Installing Networking components ...')
		call('apt-get install neutron-plugin-ml2 neutron-plugin-openvswitch-agent neutron-l3-agent '+\
		     'neutron-dhcp-agent -y', shell=True)

		c_print('Configuring the networking common components ...')

		c_print('Editing /etc/neutron/neutron.conf ...')

		if not os.path.isfile('/etc/neutron/neutron.conf.neutron-network'):
			modified_content = ''
			for line in open('/etc/neutron/neutron.conf'):
				if 'connection' in line and 'sqlite' in line:
					line = ''
				elif line == '[DEFAULT]\n':
					line += 'rpc_backend = rabbit \nrabbit_host = %s \nrabbit_password = %s\n' % (controller_ip, 'openstack') + \
						'auth_strategy = keystone\ncore_plugin = ml2\nservice_plugins = router\nallow_overlapping_ips = True\n'
				elif 'auth_host' in line:
					line = 'auth_uri = http://%s:5000/v2.0\n' % controller_ip
				elif 'auth_port' in line:
					line = 'identity_uri = http://%s:35357\n' % controller_ip
				elif 'auth_protocol' in line:
					line = '\n'
				elif 'admin_tenant_name' and '%SERVICE_TENANT_NAME%' in line:
					line = 'admin_tenant_name = service\n'
				elif 'admin_user' in line and '%SERVICE_USER%' in line:
					line = 'admin_user = neutron\n'
				elif 'admin_password' in line and '%SERVICE_PASSWORD%' in line:
					line = 'admin_password = %s\n' % 'openstack'

				modified_content += line

			print >> open('/etc/neutron/neutron.conf','w'), modified_content
			print >> open('/etc/neutron/neutron.conf.neutron-network', 'w'), 'Modified'

		c_print('Configuring the Modular Layer 2 (ML2) plug-in ...')

		if not os.path.isfile('/etc/neutron/plugins/ml2/ml2_conf.ini.modified'):
			modified_content = ''
			for line in open('/etc/neutron/plugins/ml2/ml2_conf.ini'):
				if line == '[ml2]\n':
					line += 'type_drivers = flat,gre\ntenant_network_types = gre\nmechanism_drivers = openvswitch\n'
				elif line == '[ml2_type_flat]\n':
					line += 'flat_networks = external\n'
				elif line == '[ml2_type_gre]\n':
					line += 'tunnel_id_ranges = 1:1000\n'
				elif line == '[securitygroup]\n':
					line += 'enable_security_group = True\nenable_ipset = True\n' + \
									'firewall_driver = neutron.agent.linux.iptables_firewall.OVSHybridIptablesFirewallDriver\n'

				modified_content += line

			print >> open('/etc/neutron/plugins/ml2/ml2_conf.ini', 'w'), modified_content

			tunnel_ip = raw_input('\033[36mPlease type in the IP address of the instance tunnels network interface: \033[0m')
			print >> open('/etc/neutron/plugins/ml2/ml2_conf.ini', 'a'), '[ovs]\n' + \
				'local_ip = %s \nenable_tunneling = True\n'  % tunnel_ip + \
				'bridge_mappings = external:br-ex\n' + \
				'[agent]\ntunnel_types = gre\n'

			print >> open('/etc/neutron/plugins/ml2/ml2_conf.ini.modified', 'w'), 'Modified'

		c_print('Configuring the Layer-3 (L3) agent ...')

		if not os.path.isfile('/etc/neutron/l3_agent.ini.modified'):
			print >> open('/etc/neutron/l3_agent.ini', 'a'), '' + \
							'interface_driver = neutron.agent.linux.interface.OVSInterfaceDriver\n' + \
							'use_namespaces = True\nexternal_network_bridge = br-ex\n'
			print >> open('/etc/neutron/l3_agent.ini.modified', 'w'), 'Modified'

		c_print('Configuring the DHCP agent ...')

		if not os.path.isfile('/etc/neutron/dhcp_agent.ini.modified'):
			print >> open('/etc/neutron/dhcp_agent.ini', 'a'), '' + \
							'interface_driver = neutron.agent.linux.interface.OVSInterfaceDriver\n' + \
							'dhcp_driver = neutron.agent.linux.dhcp.Dnsmasq\n' + \
							'use_namespaces = True\n'

			print >> open('/etc/neutron/dhcp_agent.ini.modified','w'), 'Modified'


		c_print('Configuring the metadata agent ...')
		c_print('Editing /etc/neutron/metadata_agent.ini ...')
		modified_content = ''
		for line in open('/etc/neutron/metadata_agent.ini'):
			if 'auth_url' in line: line = 'auth_url = http://%s:5000/v2.0\n' % controller_ip
			elif 'auth_region' in line: line = 'auth_region = regionOne\n'
			elif 'admin_tenant_name' in line and '%SERVICE_TENANT_NAME%' in line:
				line = 'admin_tenant_name = service\n'
			elif 'admin_user' in line: line = 'admin_user = neutron\n'
			elif 'admin_password' in line: line = 'admin_password = %s\n' % 'openstack'
			modified_content += line
		print >> open('/etc/neutron/metadata_agent.ini', 'w'), modified_content
		print >> open('/etc/neutron/metadata_agent.ini', 'a'), 'nova_metadata_ip = %s\n' % controller_ip + \
			'metadata_proxy_shared_secret = neutron\n' # METADATA_SECRET


		c_print('Configuring the Open vSwitch (OVS) service ...')
		c_print('Restarting the OVS service ...')
		call('service openvswitch-switch restart', shell=True)
		c_print('Adding the external bridge ...')
		external_interface = raw_input('\033[36mPlease type in the interface name that connects to the physical network '
		                               'interface: \033[0m')
		call('ovs-vsctl add-br br-ex' , shell=True)
		c_print('Adding a port to the external bridge that connects to the physical external network inter-face ...')
		call('ovs-vsctl add-port br-ex %s' % external_interface, shell=True)

		c_print('Restart the Networking services ...')
		call('service neutron-plugin-openvswitch-agent restart',shell=True)
		call('service neutron-l3-agent restart', shell=True)
		call('service neutron-dhcp-agent restart', shell=True)
		call('service neutron-metadata-agent restart', shell=True)
