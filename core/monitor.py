# coding=utf-8

from typing import Dict, List
import copy
import sys
import datetime
from os.path import join, dirname, realpath, exists
from os import mkdir
import json
import requests
import argparse
import base64

from core.utils import GetTimeStamp, Log, ErrorLevel
from core.userinfo import UserQueryManager

# header to send with every request.
PULL_REQUEST_HEADER_SKELETON = {
	'Accept': '*/*',
	'Accept-Encoding': 'gzip, deflate, sdch, br',
	'Accept-Language': 'en-US,en;q=0.8',
	'Cookie': None,
	'Origin': 'https://www.facebook.com',
	'Referer': 'https://www.facebook.com/',
	'User-Agent': None
}
JSON_PAYLOAD_PREFIX     = "for (;;);"
ONLINE_DELTA            = 3 # maybe 3 mins is when you become offline
START                   = 0 #
END                     = 1 # these two are offset for start and end timestamps
ROOT_DIR                = join(dirname(dirname(realpath(__file__))))
RESOURCE_DIR            = join(ROOT_DIR, "resources")
DEFAULT_DB_PATH         = join(RESOURCE_DIR, "database.json")
DEFAULT_CONFIG_PATH     = join(ROOT_DIR, "default.conf")
DEFAULT_UID2NAME_PATH   = join(RESOURCE_DIR, "uid2name.json")
DB_DEFAULT_STRUCTURE    = {}
DEFAULT_PULL_URL        = "https://5-edge-chat.facebook.com/pull"

class PresenceMonitor:

	def __init__(self, configPath: str, dbPath: str = DEFAULT_DB_PATH):

		### init folder structure
		self.resourcePath = RESOURCE_DIR
		if not exists(self.resourcePath):
			mkdir(self.resourcePath)

		### load DB from file
		dbFile = None
		if exists(dbPath):
			dbFile = open(dbPath, 'r')
		else:
			tmpFile = open(dbPath, 'w')
			tmpFile.write(json.dumps(DB_DEFAULT_STRUCTURE))
			tmpFile.close()
			dbFile = open(dbPath, 'r')
		self.db = json.loads(dbFile.read())
		dbFile.close()
		self.dbPath = dbPath
		Log(ErrorLevel.info, "db loaded")

		### load config file
		self.secrets = {}
		if not exists(configPath):
			Log(ErrorLevel.error, "config file path ({}) does not exist", configPath)
			sys.exit(1)
		with open(configPath) as configFile:
			for line in configFile:
				vals = line.strip().split('=', 1)
				self.secrets[vals[0].lower()] = vals[1]
		### fill up request header with valid informations from secret
		self.PullRequestHeader = PULL_REQUEST_HEADER_SKELETON
		self.PullRequestHeader["Cookie"] = self.secrets["cookie"]
		self.PullRequestHeader["User-Agent"] = self.secrets["useragent"]
		Log(ErrorLevel.info, "config loaded")

		### reset params of request header
		self.resetParameters()

		### load user manager that handles unique query logic
		self.queryManager = UserQueryManager(
			userFBID= self.secrets["uid"],
			cookie = self.secrets["cookie"],
			userAgent = self.secrets["useragent"]
		)

	def createPresence(
		self, uid: str, lastactive: int,
		online: bool, active: bool = None, mobile: bool = None
	) -> Dict:
		return {
			"uid": uid,
			"lastactive": lastactive,
			"online": online,
			"mobile": mobile,
			"active": active
		}

	def saveDB(self, isFullSave = False):
		if isFullSave:
			Log(ErrorLevel.info, "saving every record to db")
		else:
			Log(ErrorLevel.info, "saving finished records to db")
		timeStamp = GetTimeStamp()
		copiedDB = copy.deepcopy(self.db)
		for uid in copiedDB:
			for userState in ["online", "mobile", "active"]:
				user = copiedDB[uid][userState]
				if len(user) != 0:
					lastEntry = user[-1]
					if lastEntry[END] is None:
						if not isFullSave:
							# ongoing records ignored
							copiedDB[uid][userState].pop()
						else:
							# close every ongoing recording
							modifiedLastEntry = user.pop()
							modifiedLastEntry[END] = timeStamp
							user.append(modifiedLastEntry)
							copiedDB[uid][userState] = user
		# export db to json file
		with open(self.dbPath, 'w') as dbFile:
			dbFile.write(json.dumps(copiedDB))

	def saveAll(self):
		self.saveDB(isFullSave = True)

	def getRawFeedResponse(self) -> Dict:
		responseObj = None
		try:
			response_obj = requests.get(DEFAULT_PULL_URL, params=self.params, headers=self.PullRequestHeader)
			raw_response = response_obj.text
			if not raw_response:
				return None
			if raw_response.startswith(JSON_PAYLOAD_PREFIX):
				responseObj = raw_response[len(JSON_PAYLOAD_PREFIX):].strip()
				responseObj = json.loads(responseObj)
			else:
				# If it didn't start with for (;;); then something weird is happening.
				responseObj = json.loads(raw_response)
		except:
			Log(ErrorLevel.warning, "error happened while requesting json: {}", sys.exc_info()[0])
		return responseObj

	def createNewUserDB(self, uid: str):
		self.db[uid] = {
			"online": [],
			"active": [],
			"mobile": [],
			"fullname": None,
			"image": None
		}
		# get misc user info
		userInfo = self.queryManager.getUserInfo(uid)
		self.db[uid]["fullname"] = userInfo["fullname"]
		# download image, convert to 64 and save
		imageBin = requests.get(userInfo["thumbnailURL"]).content
		image64Bin = base64.b64encode(imageBin)
		image64 = image64Bin.decode('utf-8')
		self.db[uid]["image"] = image64

	def getUser(self, uid: str, state: str) -> List[List[int]]:
		if uid not in self.db:
			self.createNewUserDB(uid)
		return copy.deepcopy(self.db[uid][state])

	def setUser(self, uid: str, state: str, intervalList: List[List]):
		newValue = intervalList[-1]
		if (len(self.db[uid][state]) == 0) or (self.db[uid][state][0] != intervalList[-1][0]):
			oldValue = []
		else:
			oldValue = self.db[uid][state]
		Log(ErrorLevel.debug, "changing {}'s {} state from {} to {}", uid, state, oldValue, newValue)
		self.db[uid][state] = intervalList

	def processPresence(self, presence: Dict, state: str):
		timeIntervals = self.getUser(presence["uid"], state)
		if presence[state] is True:
			if len(timeIntervals) == 0:
				# user has no records yet of this state
				Log(ErrorLevel.debug, "{} with state {} has no records yet, create one", presence["uid"], state)
				timeIntervals.append([presence["lastactive"], None])
				self.setUser(presence["uid"], state, timeIntervals)
			else:
				# so the array is not empty
				isLastIntervalClosed = timeIntervals[-1][END] is not None
				if isLastIntervalClosed:
					# user has no open entry, start new
					Log(ErrorLevel.debug, "{} with state {} has no open entry, create new", presence["uid"], state)
					timeIntervals.append([presence["lastactive"], None])
					self.setUser(presence["uid"], state, timeIntervals)
		elif presence[state] is False:
			if len(timeIntervals) != 0:
				lastEntryOpen = timeIntervals[-1][END] is None
				if lastEntryOpen:
					modifiedLastEntry = timeIntervals.pop()
					#print("[debug]: end value of LAT: {}".format(str(presenceData["lastactive"])))
					modifiedLastEntry[END] = presence["lastactive"]
					timeIntervals.append(modifiedLastEntry)
					#print("[debug]: {} ->{} left".format(presenceType, userName))
					self.setUser(presence["uid"], state, timeIntervals)
		else:
			Log(ErrorLevel.warning, "presence value is not valid in object: {}", presence)

	def processByMatchingStates(self, presence: Dict):
		self.processPresence(presence, "online")
		if presence["active"] is not None:
			self.processPresence(presence, "active")
		if presence["mobile"] is not None:
			self.processPresence(presence, "mobile")

	def processFriendStatusList(self, chatProxyData: Dict):
		for uid in chatProxyData["buddyList"]:
			uidContent = chatProxyData["buddyList"][uid]
			if "lat" in uidContent:
				timeStamp = uidContent["lat"]
				isOnline = not self.isOlderThanDelta(timeStamp)
				if "p" in uidContent:
					isActive = (uidContent["p"] != 0) and isOnline
				elif isOnline is False:
					isActive = False # it cannot be active if not online
				else:
					isActive = None # if its still online but no presence data, we don't know
				# cancel mobile
				if isOnline is False:
					isMobile = False
				else:
					isMobile = None
				self.processByMatchingStates(self.createPresence(uid, GetTimeStamp(), isOnline, isActive, isMobile))

	def processUniqueFriendStatus(self, buddyListData: Dict):
		for uid in buddyListData["overlay"]:
			uidData = buddyListData["overlay"][uid]
			if "la" in uidData:
				timeStamp = uidData["la"]
				isOnline = not self.isOlderThanDelta(timeStamp)
				# cancel active
				if "a" in uidData:
					isActive = (uidData["a"] != 0) and isOnline
				elif isOnline is False:
					isActive = False # it cannot be active if not online
				else:
					isActive = None # still online but no presence data, we don't know
				# cancel mobile
				if isOnline is False:
					isMobile = False
				else:
					isMobile = None
				self.processByMatchingStates(self.createPresence(uid, GetTimeStamp(), isOnline, isActive, isMobile))

	def processPhoneInfo(self, phoneInfo: Dict):
		uid = phoneInfo["from"]
		self.processByMatchingStates(self.createPresence(uid, GetTimeStamp(), online=True, active=True, mobile=True))

	def processDelta(self, deltaInfo):
		if "delta" in deltaInfo:
			deltaKeyContent = deltaInfo["delta"]
			if "threadKey" in deltaKeyContent:
				threadKeyContent = deltaKeyContent["threadKey"]
				if "otherUserFbId" in threadKeyContent:
					uid = threadKeyContent["otherUserFbId"]
					self.processByMatchingStates(self.createPresence(uid, GetTimeStamp(), online=True, active=True))

	def processTyping(self, typingInfo):
		if ("u" in typingInfo) and ("ms" in typingInfo):
			ownFBID = typingInfo["u"]
			for msItem in typingInfo["ms"]:
				if (    "type" in msItem) \
					and (msItem["type"] == "typ") \
					and ("from" in msItem) \
					and (msItem["from"] != ownFBID
				):
					uid = msItem["from"]
					if ("from_mobile" in msItem["from_mobile"]):
						isMobile = msItem["from_mobile"]
					else:
						isMobile = None
					self.processByMatchingStates(self.createPresence(
						uid,
						GetTimeStamp(),
						online=True, active=True, mobile=isMobile)
					)

	def processMessageContent(self, msContent: Dict):
		for msItem in msContent:
			itemType = msItem["type"]
			if itemType == "chatproxy-presence":
				self.processFriendStatusList(msItem)
			elif itemType == "buddylist_overlay":
				self.processUniqueFriendStatus(msItem)
			elif itemType == "t_tp":
				self.processPhoneInfo(msItem)
			elif itemType == "delta":
				self.processDelta(msItem)
			elif itemType == "typ":
				self.processTyping(msItem)
			elif itemType == "inbox":
				pass # we are not interested in inbox info
			else:
				Log(ErrorLevel.debug, "unknown message type {}", msItem["type"])

	def processFeedResponse(self):
		# first we make a request to fb
		responseObj = self.getRawFeedResponse()
		# if its empty there is a problem
		if responseObj is None:
			print("[error]: request error, restarting")
			self.resetParameters()
			return
		# We got info about which pool/sticky we should be using I think??? Something to do with load balancers?
		if "lb_info" in responseObj:
			self.params["sticky_pool"] = responseObj["lb_info"]["pool"]
			self.params["sticky_token"] = responseObj["lb_info"]["sticky"]
		# seq apparently isn't tcp seq, does nothing
		if "seq" in responseObj:
			self.params["seq"] = responseObj["seq"]
		# ms contains the friends infos
		if "ms" in responseObj:
			self.processMessageContent(responseObj["ms"])
		else:
			Log(ErrorLevel.debug, "'ms' was not found in response. content: {}", responseObj)

	def isOlderThanDelta(self, secsFromEpoch: int) -> bool:
		userTimeStamp = datetime.datetime.fromtimestamp(secsFromEpoch)
		return \
			userTimeStamp < (datetime.datetime.now() - datetime.timedelta(minutes=ONLINE_DELTA))

	def isUserStateOpenedButOld(self, uid: str, state: str) -> bool:
		intervalsRef = self.getUser(uid, state)
		if len(intervalsRef) != 0:
			lastInterval = intervalsRef[-1]
			if (lastInterval[END] is None) and self.isOlderThanDelta(lastInterval[START]):
				return True
		return False

	def processQueryResponse(self):
		# get presence IF the last user status is older than time delta (3mins)
		# we don't want to be suspicious by querying every uid every time
		for uid in self.db.keys():
			if self.isUserStateOpenedButOld(uid, "online"):
				presenceData = self.queryManager.getPresence(uid)
				isOnline = presenceData["isOnline"]
				isActive = None
				isMobile = None
				if isOnline is False:
					isActive = False
					isMobile = False
				Log(ErrorLevel.debug, "query response: {} is {}", uid, ("online" if isOnline else "offline"))
				self.processByMatchingStates(self.createPresence(uid, GetTimeStamp(), isOnline, isActive, isMobile))

	def query(self):
		self.processFeedResponse()
		self.processQueryResponse()

	def resetParameters(self):
		self.params = {
			# No idea what this is.
			'cap': '8',
			# No idea what this is.
			'cb': '2qfi',
			# No idea what this is.
			'channel': 'p_' + self.secrets["uid"],
			'clientid': self.secrets["client_id"],
			'format': 'json',
			# Is this my online status?
			'idle': '0',
			# No idea what this is.
			'isq': '173180',
			# Whether to stream the HTTP GET request. We don't want to!
			# 'mode': 'stream',
			# Is this how many messages we have got from Facebook in this session so far?
			# Previous value: 26
			'msgs_recv': '0',
			# No idea what this is.
			'partition': '-2',
			# No idea what this is.
			'qp': 'y',
			# Set starting sequence number to 0.
			# This number doesn't seem to be necessary for getting the /pull content,
			# since setting it to 0 every time still gets everything as far as I can tell.
			# Maybe it's used for #webscale reasons.
			'seq': '0',
			'state': 'active',
			'sticky_pool': 'atn2c06_chat-proxy',
			'sticky_token': '0',
			'uid': self.secrets["uid"],
			'viewer_uid': self.secrets["uid"],
			'wtc': '171%2C170%2C0.000%2C171%2C171'
		}