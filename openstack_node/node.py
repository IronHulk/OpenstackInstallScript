import os
import sys
import socket
import fcntl
import struct
import shutil
from subprocess import Popen, PIPE, call
from utils.tools import e_print, c_print

__author__ = 'Fernando Zhu'

class OpenstackNode():
	current_ip = ''
	def __init__(self):
		self.logo()
		try:
			self.current_ip = self.get_ip()
		except:
			self.current_ip = raw_input('\033[36mPlease type in the ip address for current node :\033[0m')


	def logo(self):
		print ('\033[36m' + '''
     ____                        __             __
    / __ \____  ___  ____  _____/ /_____ ______/ /__
   / / / / __ \/ _ \/ __ \/ ___/ __/ __ `/ ___/ //_/
  / /_/ / /_/ /  __/ / / (__  ) /_/ /_/ / /__/ ,<
  \____/ .___/\___/_/ /_/____/\__/\__,_/\___/_/|_|
      /_/
''' + '\033[0m')

	def get_ip(self):
		message = Popen('ifconfig', shell=True, stdout=PIPE).communicate()
		interface = message[0].split()[0]
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		inet = fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', interface[:15]))
		ret = socket.inet_ntoa(inet[20:24])
		return ret

	def add_admin_env(self, current_ip):
		os.environ['OS_TENANT_NAME'] = 'admin'
		os.environ['OS_USERNAME'] = 'admin'
		os.environ['OS_PASSWORD'] = 'openstack'
		os.environ['OS_AUTH_URL'] = 'http://' + current_ip + ':35357/v2.0'

	def add_demo_env(self, current_ip):
		os.environ['OS_TENANT_NAME'] = 'demo'
		os.environ['OS_USERNAME'] = 'demo'
		os.environ['OS_PASSWORD'] = 'openstack'
		os.environ['OS_AUTH_URL'] = 'http://' + current_ip + ':5000/v2.0'

	def del_env(self):
		del os.environ['OS_TENANT_NAME']
		del os.environ['OS_USERNAME']
		del os.environ['OS_PASSWORD']
		del os.environ['OS_AUTH_URL']

	def db_create(self, db_name):
		try:
			import MySQLdb
			connection = MySQLdb.connect(host='localhost',user='root',passwd='openstack',port=3306)
			cur=connection.cursor()
			cur.execute('create database '+db_name)
			cur.execute("grant all privileges on "+db_name+".* to '"+db_name+"'@'127.0.0.1' identified by 'openstack'")
			cur.execute("grant all privileges on "+db_name+".* to '"+db_name+"'@'%' identified by 'openstack'")
			cur.close()
			connection.commit()
			connection.close()

		except ImportError:
			e_print("MySQLdb doesn't exist")
		except:
			e_print('Error ocurred when creating database')
			sys.exit()

	def keyring_setup(self):
		c_print('Installing cloud archive keyring...')
		call('apt-get install ubuntu-cloud-keyring', shell=True)
		c_print('Installing PUBKEY')
		call('apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 5EDB1B62EC4926EA', shell=True)

		c_print('Checking ubuntu cloud archive keyring...')
		if os.path.isfile('/etc/apt/sources.list.d/cloudarchive-juno.list') is False:
			c_print('Adding cloud archive keyring...')
			cloudarchive = open('cloudarchive-juno.list', 'w')
			print >> cloudarchive, 'deb http://ubuntu-cloud.archive.canonical.com/ubuntu trusty-updates/juno main'
			cloudarchive.close()
			shutil.move('./cloudarchive-juno.list', '/etc/apt/sources.list.d/')
			print 'Done'+'\033[0m'

		c_print('Updating package list...')
		call('apt-get update',shell=True)
		c_print('Upgrading system...')
		call('apt-get dist-upgrade -y',shell=True)

	def prepare_pkg(self):
		pass

	def config(self):
		pass

	def install(self):
		pass

	def chusr_normal(self):
		c_print('Dropping superuser privilege...')
		c_print('Switching back to user %s with uid %s...\033[0m' % (os.environ['SUDO_USER'], os.environ['SUDO_UID']))
		os.seteuid(int(os.environ['SUDO_UID']))

	def chusr_sudo(self):
		c_print('Getting back the superuser privilege...')
		os.seteuid(0)
