#This script, Meetup Instant RSVP, when run in the crontab (recommended to run once every 15 minutes!) will automatically
#RSVP all possible events in your specified list of Meetup groups where you are a member.
#You need to install the python libraries below from the imports. Only tested on Python 3.5+, probably needs a few changes for 2.7.
#You must have these two libraries: pip install pytz httplib2
#For Google Calendar, install: pip install --upgrade google-api-python-client
#Also, for Twilio, pip install twilio.
#For Google Calendar, follow these instructions to activate Google Calendar API: https://developers.google.com/google-apps/calendar/quickstart/python
#You will need to download the json file (client_secret.json) into .credentials directory inside your script user's home directory
#First, you must run this script via command line before putting on crontab since you will need to verify the OAuth2 URL with Google Calendar API
#For the crontab entry, here is the recommended command for the entry: */15 * * * * /usr/bin/python3 /path/to/scripts/meetup-rsvp-gh.py  >> /var/log/meetup.log 2>&1
#This entry will include logging into a file in /var/log/meetup.log . If you don't want that, just do: */15 * * * * /usr/bin/python3 /path/to/scripts/meetup-rsvp-gh.py > /dev/null 2>&1

from __future__ import print_function
import httplib2
import os

import json
import urllib.request
import re

import time
import pytz
from datetime import datetime, timedelta
from pytz import timezone

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

from twilio.rest import TwilioRestClient

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

SCOPES = 'https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Meetup Instant RSVP Notifier'

#These are group url names (get this value by going to the Meeetup group's homepage and get the directory in the URL)
target_groups = ["New-York-Big-Data-Workshop", "nycjava"]

my_kind = "event_announce"
#Your Meetup API key. This can be obtained by going to the Meetup API page for API Key
myID = "abc123"

url = "https://api.meetup.com/3/notifications?key=" + myID + "&sign=true"
eventsURL = "https://api.meetup.com/%s/events/%s?photo-host=public&key=" + myID
allEventsURLFormatter = "https://api.meetup.com/%s/events?photo-host=public&page=20&key=" + myID + "&status=upcoming,proposed"
rsvpURL = "https://api.meetup.com/2/rsvp"
myEventsURL = "https://api.meetup.com/self/events?photo-host=public&page=20&key=" + myID

#Your Meetup member ID. You can get it from your Meetup profile page
member_id = "1234567890"
checkProposedEventsRSVPURL = "https://api.meetup.com/2/events?member_id=" + member_id + "&offset=0&format=json&limited_events=False&rsvp=yes,waitlist&photo-host=public" + "&page=20&fields=&order=time&status=upcoming,proposed&desc=false&key=" + myID
current_milli_time = lambda: int(round(time.time() * 1000))

#These are values from Twilio. Create a developer account and register a new app to obtain these values
ACCOUNT_SID = 'INSERT_ACCOUNT_SID_HERE'
AUTH_TOKEN = 'INSERT_AUTH_TOKEN_HERE'

#Twilio SMS recipient's number
toNum = "+19095550000"

#Twilio SMS from number
fromNum = "+19195550000"
rsvpdEvents = {}

#Google Calendar and Twilio are optional. You can disable here
enableGoogleCalendar = True
enableTwilio = True

#Change according to the Timezone you need. Values found here for pytzTZ: http://stackoverflow.com/questions/13866926/python-pytz-list-of-timezones
# And for myTimezone: http://stackoverflow.com/questions/22526635/list-of-acceptable-google-calendar-api-time-zones
myTimezone = 'America/Los_Angeles'
pytzTZ = 'US/Pacific'

#Click on your calendar's settings in Google Calendar for the ID
yourCalendarID = "abc123@gmail.com"

#Notifications in Google Calendar before event in minutes
minsToEmail = 48 * 60
minsToPopup = 10

def addToGoogleCalendar(target_group_urlname, event_name, location, time, response):
    if enableGoogleCalendar:
        credentials = get_credentials()
        http = credentials.authorize(httplib2.Http())
        service = discovery.build('calendar', 'v3', http=http)
        event = {
          'summary': event_name,
          'location': location,
          'description': target_group_urlname,
          'start': {
            'dateTime': str(time.isoformat()),
            'timeZone': myTimezone,
          },
          'end': {
          #3 Hours set because Google Calendar needs a concrete end time which Meetup doesn't always have
            'dateTime': str((time + timedelta(hours = 3)).isoformat()),
            'timeZone': myTimezone,
          },
          'reminders': {
            'useDefault': False,
            'overrides': [
            #These values can be customized
              {'method': 'email', 'minutes': minsToEmail },
              {'method': 'popup', 'minutes': minsToPopup },
            ],
          },
        }

        event = service.events().insert(calendarId=yourCalendarID, body=event).execute()
        print('Event created: %s' % (event.get('htmlLink')))

def get_credentials():
    #This function taken from Google API docs, but modified for the file location of the secret file
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-python-quickstart.json')

    client_secret_file = os.path.join(credential_dir,
                                   CLIENT_SECRET_FILE)

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(client_secret_file, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def rsvp(event_id, event_name, target_group_urlname):

    params = urllib.parse.urlencode({'rsvp': "yes", "key" : myID, "event_id": event_id}).encode()

    try:
        f = urllib.request.urlopen(rsvpURL, params)
        string = f.read()
        string = string.decode('utf-8')
    except urllib.error.HTTPError as e:
        print("Failure: " + str(e.code))
        print(e.read())
    else:
        string = json.loads(string)
        print("RSVP result: " + str(string))
        if "time" not in string["event"]:
            if "venue" not in string:
                location = "location TBD"
            else:
                location = string["venue"]["name"] + "," + string["venue"]["address_1"] + "," + string["venue"]["city"]
            sendTwilio(target_group_urlname, event_name, event_id, location, toNum , fromNum, "!!upcoming!!", string["response"])
        elif "venue" not in string:
            theTime = string["event"]["time"] / 1000
            print("The time: " + str(theTime))
            tz = pytz.timezone(pytzTZ)
            dateTime = datetime.fromtimestamp(theTime, tz)
            sendTwilio(target_group_urlname, event_name, event_id, "location TBD", toNum , fromNum, str(dateTime),  string["response"])
            addToGoogleCalendar(target_group_urlname, event_name, "location TBD", dateTime, string["response"])
        else:
            theTime = string["event"]["time"] / 1000
            print("The time: " + str(theTime))
            tz = pytz.timezone(pytzTZ)
            dateTime = datetime.fromtimestamp(theTime, tz)
            location = string["venue"]["name"] + "," + string["venue"]["address_1"] + "," + string["venue"]["city"]
            sendTwilio(target_group_urlname, event_name, event_id, location, toNum , fromNum, str(dateTime),  string["response"])
            addToGoogleCalendar(target_group_urlname, event_name, location, dateTime, string["response"])


def sendTwilio(target_group_urlname, event_name, event_id, venue, toNum , fromNum, time, status ):

    if enableTwilio:
        client = TwilioRestClient(ACCOUNT_SID, AUTH_TOKEN)

        message = client.messages.create(
            body="Just RSVP " + status + " successfully to " + target_group_urlname + " for event " + event_name + " at " + venue + " on " + time + "."  # Message body, if any
            to=toNum,
            from_=fromNum,
        )
        print("Twilio Message SID: " + message.sid)

def getAllEvents(allEventsURL):
    f = urllib.request.urlopen(allEventsURL)
    string = f.read()
    string = string.decode('utf-8')
    string = json.loads(string)

    for x in string:
        if "status" not in x:
            continue
        elif x["status"] == "upcoming" or x["status"] == "proposed":
            print("Ok, preparing to RSVP...x['id']: " + x['id'])
            if x["group"]["urlname"]:
                if x["group"]["urlname"] in rsvpdEvents:
                    if x['id'] in rsvpdEvents[x["group"]["urlname"]]:
                        print("Ignoring " + x['id'] + " because its already RSVPed")
                        continue
            rsvp(x["id"], x["name"], x["group"]["urlname"])

def getMyEvents():
    grabMyEventsPerPage(myEventsURL)

def grabMyEventsPerPage(loopURL):
    f = urllib.request.urlopen(loopURL)
    string = f.read()
    string = string.decode('utf-8')
    string = json.loads(string)

    for x in string:
        print("Adding " + x["group"]["urlname"] + " id : " + x["id"] + " to internal memory")
        if x["group"]["urlname"] not in rsvpdEvents:
            print(x["group"]["urlname"] + " not in rsvpdEvents")
            rsvpdEvents[x["group"]["urlname"]] = set([])
        rsvpdEvents[x["group"]["urlname"]].add(x["id"])

    links = f.info().get_all("LINK")
    if links is not None:
        for ax in links:
            y = re.match('<(.*?)>; rel="next"', ax)
            if y is not None:
                loopURL = y.group(1) + "&key=" + myID
                print("URL for next: " + loopURL)
                grabMyEventsPerPage(loopURL)
            else:
                continue

def checkProposedEventsRSVP():
    f = urllib.request.urlopen(checkProposedEventsRSVPURL)
    print("The url: " + checkProposedEventsRSVPURL)
    string = f.read()
    string = string.decode('utf-8')
    string = json.loads(string)

    if "results" not in string:
        pass
    else:
        for x in string["results"]:
            if x["group"]["urlname"] not in rsvpdEvents:
                rsvpdEvents[x["group"]["urlname"]] = set([])
            rsvpdEvents[x["group"]["urlname"]].add(x["id"])
            print("Adding proposed: " + x["id"])

if __name__ == "__main__":
    print("===========================================================================")
    tz = pytz.timezone(pytzTZ)
    dateTime = datetime.now(tz)

    checkProposedEventsRSVP()
    getMyEvents()

    for grpName in target_groups:
        getAllEvents(allEventsURLFormatter % grpName)
