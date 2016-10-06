# meetup-instant-rsvp
This script, Meetup Instant RSVP, when run in the crontab (recommended to run once every 15 minutes!) will automatically RSVP all possible events in your specified list of Meetup groups where you are a member. You can be notified via Google Calendar and Twilio SMS

Instructions:
This script, Meetup Instant RSVP, when run in the crontab (recommended to run once every 15 minutes!) will automatically
#RSVP all possible events in your specified list of Meetup groups where you are a member.

You need to install the python libraries below from the imports. Only tested on Python 3.5+, probably needs a few changes for 2.7.

You must have these two libraries: pip install pytz httplib2

For Google Calendar, install: pip install --upgrade google-api-python-client

Also, for Twilio, pip install twilio.

For Google Calendar, follow these instructions to activate Google Calendar API: https://developers.google.com/google-apps/calendar/quickstart/python

You will need to download the json file (client_secret.json) into .credentials directory inside your script user's home directory

Firstly, you must run this script via command line before putting on crontab since you will need to verify the OAuth2 URL with Google Calendar API

For the crontab entry, here is the recommended command for the entry: */15 * * * * /usr/bin/python3 /path/to/scripts/meetup-rsvp-gh.py  >> /var/log/meetup.log 2>&1

That entry will include logging into a file in /var/log/meetup.log . If you don't want that, just use: */15 * * * * /usr/bin/python3 /path/to/scripts/meetup-rsvp-gh.py > /dev/null 2>&1
