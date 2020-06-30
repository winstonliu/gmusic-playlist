# Author: John Elkins <john.elkins@yahoo.com>
# License: MIT <LICENSE>

__version__ = '0.160530'

__required_gmusicapi_version__ = '10.0.0'

from collections import Counter
from gmusicapi import __version__ as gmusicapi_version
from gmusicapi import Mobileclient
from gmusicapi.exceptions import CallFailure
from preferences import *
import re
import time
import getpass
import sys
import os
import codecs

# the api to use for accessing google music
api = None

# the logfile for keeping track of things
logfile = None

# provide a shortcut for track_info_separator
tsep = track_info_separator

# flag indicating if account is all access capable
allaccess = True

# check for debug set via cmd line
if '-dDEBUG' in sys.argv:
    debug = True

# check versions
def assert_prerequisites():

    required = __required_gmusicapi_version__
    actual = gmusicapi_version
    
    def version(ver):
        return int(re.sub(r'\D','',ver))

    if ( version(actual) < version(required) ):
        log("ERROR gmusicapi version of at least "+required+" is required. ")
        exit()

# loads the personal library
def load_personal_library():
    plog('Loading personal library... ')
    plib = api.get_all_songs()
    log('done. '+str(len(plib))+' personal tracks loaded.')
    return plib

# opens the log for writing
def open_log(filename):
    global logfile
    logfile = codecs.open(filename, encoding='utf-8', mode='w', buffering=1)
    return logfile

# closes the log
def close_log():
    if logfile:
        logfile.close()

# logs to both the console and log file if it exists
def log(message, nl = True):
    if nl:
        message += os.linesep
    print(str(message))
    if logfile:
        logfile.write(message)

# logs a message if debug is true
def dlog(message):
    if debug:
        log(message)

# logs a progress message (a message without a line return)
def plog(message):
    log(message, nl = False)

# search all access
def aa_search(search_string,max_results):
    global allaccess
    results = []
    if allaccess:
        try:
            results = api.search(search_string,
                    max_results=max_results).get('song_hits')
        except CallFailure:
            allaccess = False
            log('WARNING no all access subscription detected. '+
                ' all access search disabled.')
    return results

# gets the track details available for google tracks
def get_google_track_details(sample_song = 'one u2'):
    results = aa_search(sample_song,1)
    if len(results):
        return (results[0].get('track').keys())
    return "['title','artist','album']"

# creates result details from the given track
def create_result_details(track):
    result_details = {}
    for key, value in track.items():
        result_details[key] = value
    result_details['songid'] = (track.get('storeId')
        if track.get('storeId') else track.get('id'))
    return result_details

# creates details dictionary based off the given details list
def create_details(details_list):
    details = {}
    details['artist'] = None
    details['album'] = None
    details['title'] = None
    details['songid'] = None
    if len(details_list) < 2:
        return details
    for pos, nfo in enumerate(details_list):
        if len(track_info_order) <= pos:
            continue
        details[track_info_order[pos]] = nfo.strip()
    return details

# split a csv line into it's separate fields
def get_csv_fields(csvString,sepChar=tsep):
    fields = []
    fieldValue = u''
    ignoreTsep = False
    for c in csvString:
        if c == sepChar and not ignoreTsep:
            fields.append(handle_quote_input(fieldValue))
            fieldValue = u''
            continue
        elif c == '"':
            ignoreTsep = (not ignoreTsep)
        fieldValue += c
    fields.append(handle_quote_input(fieldValue))
    return fields

# add quotes around a csv field and return the quoted field
def handle_quote_output(aString):
  """ See: https://en.wikipedia.org/wiki/Comma-separated_values#Basic_rules_and_examples """
  if aString.find('"') > -1 or aString.find(tsep) > -1:
    return '"%s"' % aString.replace('"', '""')
  else:
    return aString

# remove the quotes from around a csv field, and return the unquoted field
def handle_quote_input(aString):
  if len(aString) > 0 and aString[0] == '"' and aString[-1] == '"':
      return aString[1:-1].replace('""', '"')
  else:
      return aString

# creates details string based off the given details dictionary
def create_details_string(details_dict, skip_id = False):
    out_string = u''
    for nfo in track_info_order:
        if skip_id and nfo == 'songid':
            continue
        if len(out_string) != 0:
            out_string += track_info_separator
        try:
            out_string += handle_quote_output(str(details_dict[nfo]))
        except KeyError:
            # some songs don't have info like year, genre, etc
            pass
    return out_string

# logs into google music api
def open_api():
    global api
    log('Logging into google music...')
    
    # Attempt to login
    api = Mobileclient()
    logged_in = api.oauth_login(Mobileclient.FROM_MAC_ADDRESS)

    if not logged_in:
        log('No oauth credentials found, please authenticate your account!')

        # Performs oauth and stores generated credentials to Appdirs 
        # 'user_data_dir' by default. oauth only needs to be performed once per 
        # machine if the credentials are stored, which is the default behavior.
        authenticated = api.perform_oauth(open_browser=True)
    else:
        log('Successfully logged in!')

    dlog(u'Available track details: ' + str(get_google_track_details()))
    return api

# logs out of the google music api
def close_api():
    if api:
        api.logout()

# creates a stats dictionary
def create_stats():
    stats = {}
    stats['genres'] = []
    stats['artists'] = []
    stats['years'] = []
    stats['total_playcount'] = 0
    return stats

# updates the stats dictionary with info from the track
def update_stats(track,stats):
    stats['artists'].append(track.get('artist'))
    if track.get('genre'): stats['genres'].append(track.get('genre'))
    if track.get('year'): stats['years'].append(track.get('year'))
    if track.get('playCount'): stats['total_playcount'] += track.get(
        'playCount')

# calculates stats
def calculate_stats_results(stats,total_tracks):
    results = {}
    results['genres'] = Counter(stats['genres'])
    results['artists'] = Counter(stats['artists'])
    results['years'] = Counter(stats['years'])
    results['playback_ratio'] = stats['total_playcount']/float(total_tracks)
    return results    

# logs the stats results
def log_stats(results):
    log(u'top 3 genres: '+repr(results['genres'].most_common(3)))
    log(u'top 3 artists: '+repr(results['artists'].most_common(3)))
    log(u'top 3 years: '+repr(results['years'].most_common(3)))
    log(u'playlist playback ratio: ' + str(results['playback_ratio']))

# display version and check prerequisites
log("gmusic-playlist: "+__version__)
log("gmusicapi: "+gmusicapi_version)
assert_prerequisites();
