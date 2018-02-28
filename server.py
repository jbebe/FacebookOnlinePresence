# coding=utf-8

from traceback import format_exc
from typing import List
from argparse import ArgumentParser, Namespace
from os import path
from sys import exit
from threading import Thread
from time import sleep

from core import globals
from core.utils import ErrorLevel, Log
from core.monitor import PresenceMonitor

def StartPresenceMonitor(args: Namespace):
	if args.log is not None:
		globals.LOG_LEVEL = int(args.log[0])
	args.config = args.config[0]
	if args.db is None:
		pm = PresenceMonitor(args.config)
	else:
		pm = PresenceMonitor(args.config, args.db)
	counter = 0
	saveCount = 10 # db save frequency
	sleepTime = 2  # sleep between two monitor action
	globals.RUN_PROGRAM = True
	while globals.RUN_PROGRAM:
		try:
			pm.query()
			counter = (counter + 1) % saveCount
			if counter == 0:
				pm.saveDB()
			sleep(sleepTime)
		except:
			Log(ErrorLevel.warning, "{}", format_exc())
			pm.resetParameters()
	pm.saveAll()

def InitArguments() -> List[List[str]]:
	parser = ArgumentParser(
		prog="python " + path.basename(__file__),
		description="This is the server side of the presence monitor. "
		            "It collects presence data from facebook.",
		epilog="Author: Bálint Juhász"
	)
	parser.add_argument(
		"-c", "--config",
		metavar='CONFIG_FILE', nargs=1, required=True,
		help="Path to the config file"
	)
	parser.add_argument(
		"-d", "--db",
		metavar='DB_FILE', nargs=1, required=False,
		help="Path to the db json-file"
	)
	parser.add_argument(
		"-l", "--log",
		metavar='LOG_LEVEL', nargs=1, required=False,
		help="0: silent, 1: error, 2: warning (default), 3: info, 4: debug"
	)
	return parser.parse_args()

def main():
	globals.LOG_LEVEL = ErrorLevel.warning # default log level
	cmdArgs = InitArguments()
	thread = Thread(target=StartPresenceMonitor, args=(cmdArgs,))
	thread.start()
	# the while loop makes sure we wait for ^C
	# if the press shows up we change the running flag
	# to stop the monitoring thread
	try:
		while thread.is_alive():
			sleep(1)
	except KeyboardInterrupt:
		globals.RUN_PROGRAM = False
		Log(ErrorLevel.info, "please wait (and don't tap on CTRL-C) while the long-lived tcp connection ends")
	if thread.is_alive():
		thread.join()
	return 0

if __name__ == "__main__":
	exit(main())