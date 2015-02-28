from subprocess import call

__author__ = 'Fernando Zhu'


def c_print(str_arg):
	print('\033[33m'+str_arg+'\033[0m')


def e_print(str_arg):
	print('\033[35m'+str_arg+'\033[0m')

