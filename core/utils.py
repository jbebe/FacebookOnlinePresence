# coding=utf-8

from core import globals
from datetime import datetime

class ErrorLevel:
	silent  = 0
	error   = 1
	warning = 2
	info    = 3
	debug   = 4

def Log(errorLevel: int, formatString: str, *args, **kwargs):
	if errorLevel <= globals.LOG_LEVEL:
		print(formatString.format(*args), **kwargs)

def GetTimeStamp():
	return int(
		(datetime.now() - datetime.utcfromtimestamp(0)).total_seconds()
	)