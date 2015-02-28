import sys
import argparse
from utils.tools import e_print,c_print
__author__ = 'Fernando Zhu'

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument('node_type', help = '\033[33mPlease specify the node type. i.e. controller, compute, '
	                                        'nova-network, neutron-network\033[0m')
	args = parser.parse_args()

	if args.node_type == 'controller':
		from controller_node.controller import ControllerNode
		ControllerNode().install()

	elif args.node_type == 'compute':

		c_print('Avaliable network: ')
		c_print('1. Neutron Network\n2. Nova Network(legacy network)\n')
		network_type = raw_input('\033[36mPlease choose the network you want to install\033[0m: ')
		if int(network_type) == 1:

			from compute_node.compute import ComputeNode
			ComputeNode().install()
			ComputeNode().neutron()

		elif int(network_type) == 2:

			from compute_node.compute import ComputeNode
			ComputeNode().install()

		else:
			e_print('Invalid network type, please try again')
			sys.exit()

	elif args.node_type == 'network':

		c_print('Installing neturon network ...')
		from network_node.network import NeutronNetwork
		NeutronNetwork().install()

	elif args.node_type == 'controller-telemetry':
		from controller_node.controller import ControllerNode
		ControllerNode().telemetry()

	elif args.node_type == 'compute-telemetry':
		from compute_node.compute import ComputeNode
		ComputeNode().telemetry()

	else:
		e_print('Node type does not exist. Please check again')
		sys.exit()

if __name__ == '__main__':
	main()
