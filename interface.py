# coding=utf-8

import sys
import os
import argparse
import flask

app = flask.Flask(__name__, static_folder="interface")
DBPath = None # type: str

@app.route("/")
def root():
	return app.send_static_file("index.html")

@app.route("/db")
def db():
	with open(DBPath) as jsonDB:
		return jsonDB.read()

def main():
	global DBPath
	parser = argparse.ArgumentParser(
		prog="python " + os.path.basename(__file__),
		description="Description of the program",
		epilog="Epologue of the program"
	)
	parser.add_argument(
		"-d", "--db",
		metavar='DB_FILE', nargs=1, required=True,
		help="Path to the database file"
	)
	args = parser.parse_args()
	DBPath = args.db[0]
	app.run(host="0.0.0.0")

if __name__ == "__main__":
	sys.exit(main())