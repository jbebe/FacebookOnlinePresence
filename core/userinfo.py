# coding=utf-8

from typing import Dict, List
import sys
import json
import re
import requests

from core.utils import Log, ErrorLevel

JSON_PAYLOAD_PREFIX = "for (;;);"
WEBSITE_URL         = "https://www.facebook.com/"
INFORMATION_URL     = "https://www.facebook.com/chat/user_info/?dpr=1"
PRESENCE_URL        = "https://www.facebook.com/ajax/mercury/tabs_presence.php?dpr=1"

class UserQueryManager:

	def __init__(self, userFBID: str, cookie: str, userAgent: str):
		self.user_fbid = userFBID
		self.initHeaders(userFBID, cookie, userAgent)

	@staticmethod
	def getParsedResponse(rawResponse: str) -> Dict:
		if not rawResponse:
			data = None
		elif rawResponse.startswith(JSON_PAYLOAD_PREFIX):
			data = rawResponse[len(JSON_PAYLOAD_PREFIX):].strip()
			data = json.loads(data)
		else:
			# If it didn't start with for (;;); then something weird is happening.
			data = json.loads(rawResponse)
		return data

	@staticmethod
	def getParsedPresenceInfo(rawResponse: str) -> Dict:
		result = { "isOnline": None }
		Log(ErrorLevel.debug, "query presence raw response: {}", rawResponse)
		responseObj = UserQueryManager.getParsedResponse(rawResponse)
		if ("payload" in responseObj) \
			and (responseObj["payload"] is dict) \
			and ("availability" in responseObj["payload"]
		):
			availabilityObj = responseObj["payload"]["availability"]
			availabilityIDs = availabilityObj.keys()
			if len(availabilityIDs) == 1:
				availabilityValue = availabilityObj[next(iter(availabilityIDs))]
				result["isOnline"] = (availabilityValue != 0)
		return result

	@staticmethod
	def getParsedOneUserInfo(profileValue: dict, result: dict) -> Dict:
		result["fullname"] = profileValue["name"]
		result["thumbnailURL"] = profileValue["thumbSrc"]
		return result

	@staticmethod
	def getParsedAllUserInfo(profilesObj: dict, result: dict) -> Dict:
		resultDict = {}
		for uid in profilesObj:
			resultDict[uid] = UserQueryManager.getParsedOneUserInfo(profilesObj[uid], result.copy())
		return resultDict

	@staticmethod
	def getParsedUserInfo(rawResponse: str) -> Dict:
		result = {
			"fullname": None,
			"thumbnailURL": None,
		}
		responseObj = UserQueryManager.getParsedResponse(rawResponse)
		if  (   ("payload" in responseObj)
			and (type(responseObj["payload"]) is dict)
			and ("profiles" in responseObj["payload"])
		):
			profilesObj = responseObj["payload"]["profiles"]
			profileIDs = profilesObj.keys()
			if len(profileIDs) == 1:
				profileValue = profilesObj[next(iter(profileIDs))]
				result = UserQueryManager.getParsedOneUserInfo(profileValue, result)
			else:
				result = UserQueryManager.getParsedAllUserInfo(profilesObj, result)
		else:
			Log(ErrorLevel.warning, "unexpected user info: {}", responseObj)
		return result

	def getUserInfo(self, uid: str) -> Dict:
		infoBody = self.INFORMATION_REQUEST_BODY.copy()
		infoBody["ids[0]"] = uid
		response_obj = requests.post(
			INFORMATION_URL,
			data = infoBody,
			headers = self.JSON_POST_HEADERS
		)
		Log(ErrorLevel.debug, "raw query response: {}", response_obj.text)
		userInfo = self.getParsedUserInfo(response_obj.text)
		return userInfo

	def getAllUserInfo(self, uidList: list) -> Dict:
		infoBody = self.INFORMATION_REQUEST_BODY.copy()
		for i, uid in enumerate(uidList):
			infoBody["ids[{}]".format(i)] = str(uid)
			response_obj = requests.post(
				INFORMATION_URL,
			    data=infoBody,
			    headers=self.JSON_POST_HEADERS
			)
		return UserQueryManager.getParsedUserInfo(response_obj.text)

	def getPresence(self, uid: str) -> Dict:
		presenceBody = self.PRESENCE_REQUEST_BODY.copy()
		presenceBody["target_id"] = uid
		presenceHead = self.JSON_POST_HEADERS.copy()
		presenceHead["content-length"] = \
			str(len("&".join([
				"{}={}".format(key, value)
				for (key, value) in zip(presenceBody.keys(), presenceBody.values())
			])))
		response_obj = requests.post(
			PRESENCE_URL,
			data=presenceBody,
			headers=presenceHead
		)
		return self.getParsedPresenceInfo(response_obj.text)

	def getToken(self) -> str:
		if hasattr(self, "token"):
			return self.token
		else:
			response_obj = requests.get(
				WEBSITE_URL,
				headers=self.WEBSITE_REQUEST_HEADERS,
				allow_redirects=True
			)
			matchTokenRegex = """name="fb_dtsg" ?value="([^\\"]+)""" # matching attribute in html with regex
			m = re.search(matchTokenRegex, response_obj.text)
			if m:
				self.token = m.group(1)
				return self.token
			else:
				Log(ErrorLevel.error, "token is missing from fb main page or invalid data in config file")
				sys.exit(1)

	def initHeaders(self, user_fbid, cookie: str, userAgent: str):
		self.WEBSITE_REQUEST_HEADERS = {
			"accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
			"accept-encoding": "gzip, deflate, sdch",
			"accept-language": "en-US,en;q=0.8",
			"cache-control": "no-cache",
			"cookie": cookie,
			"pragma": "no-cache",
			"upgrade-insecure-requests": "1",
			"user-agent": userAgent
		}
		self.JSON_POST_HEADERS = {
			"accept": "*/*",
			"accept-encoding": "gzip, deflate",
			"accept-language": "en-US,en;q=0.8",
			"cache-control": "no-cache",
			"content-length": None,
			"content-type": "application/x-www-form-urlencoded",
			"cookie": cookie,
			"origin": "https://www.facebook.com",
			"pragma": "no-cache",
			"referer": "https://www.facebook.com/",
			"user-agent": userAgent
		}
		self.INFORMATION_REQUEST_BODY = {
			#"ids[0]": None,
			# ids[1] : another one
			# ids[2] : another one
			"__user": user_fbid,
			"__a": "1",
			"__dyn": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
			         "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
					 "ABCDEFGHIJ_LMNOPQRSTUVWXYZabcdefghijkl", # this isn't needed
			"__af": "m",
			"__req": "q",
			"__be": "-1",
			"__pc": "PHASED:DEFAULT",
			"__rev": "2702404",
			"fb_dtsg": self.getToken(),
			"ttstamp": "26512345678901234567890123456789012345678901234567890123456" # this isn't needed either
		}
		self.PRESENCE_REQUEST_BODY = {
			"target_id": None,
			"__user": user_fbid,
			"__a": "1",
			"__dyn": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
			         "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
					 "ABCDEFGHIJ_LMNOPQRSTUVWXYZabcdefghijkl",
			"__af": "m",
			"__req": "5",
			"__be": "-1",
			"__pc": "PHASED:DEFAULT",
			"__rev": "2702404",
			"fb_dtsg": self.getToken(),
			"ttstamp": "26512345678901234567890123456789012345678901234567890123456"
		}

