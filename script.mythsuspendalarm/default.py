import MySQLdb
import _mysql
from datetime import datetime, timedelta
import subprocess
import os
import time
import sys
import xbmc, xbmcgui, xbmcplugin, xbmcaddon
import simplejson as json
import MythStatus


fail=False
abort=xbmcgui.DialogProgress()
cronMode=False
mythBackend=MythStatus
errorMessage="MythSuspendAlarm: "

__ScriptName__ = "XBMC Myth Suspend Alarm"
__ScriptVersion__ = "0.1.0"
__Author__ = "el_Paraguayo"
__Website__ = ""

_A_ = xbmcaddon.Addon( "script.mythsuspendalarm" )
_S_ = _A_.getSetting

#Get user variables
#These are set via settings option in XBMC
#xbmcplugin.openSettings()

#Abort time (in seconds) - gives the user time to abort the script if
#necessary
boottime=int(_S_( "boottime" ))

#Minimum time (in minutes) until next recording
#if next recording < this - computer won't powerdown.
#Can be set to 0
minshutdown = int(_S_( "minshutdown" ))

#Wake up time (in seconds) i.e. if you want your machine to reboot 5 mins
#before next recording use boottime=300
aborttime=int(_S_( "aborttime" ))

#Some BIOSes need alarm time in UTC, others need an incremental amount
#e.g. +300 for 5 minutes in the future
alarmtype=int(_S_( "alarmtype" ))

#Select whether machine should suspend or hibernate.
actionfunction=["Suspend", "Hibernate"]
actiontype=int(_S_( "actiontype" ))

#Session types to check for before suspend (uses netstat).
sessiontypes=str(_S_( "sessiontypes" ))

#Path for alarm set script
#NB this must be set to run with no password in sudoers
alarmscript=_S_( "alarmscript" )

#Path for myth backend status script
#NB this must be set to run with no password in sudoers
statusscript=_S_( "statusscript" )

#MySQL details
sqlhost=_S_( "sqlhost" )
sqluser=_S_( "sqluser" )
sqlpw=_S_( "sqlpw" )
sqldb=_S_( "sqldb" )

#Are we running as a cron job?
if len(sys.argv) > 1:
  if sys.argv[1] ==  "cron":
    cronMode=True

def getMythTimes():
  # connect
  db = MySQLdb.connect(host=sqlhost, user=sqluser, passwd=sqlpw, db=sqldb)
  # create a cursor
  cursor = db.cursor()
  nextrecsql = "SELECT recordmatch.starttime, record.title FROM recordmatch INNER JOIN record on recordmatch.recordid=record.recordid WHERE recordmatch.starttime>now() and recordmatch.oldrecduplicate=0 and recordmatch.recduplicate=0 and recordmatch.findduplicate=0 and recordmatch.oldrecstatus is null order by recordmatch.starttime ASC LIMIT 0,1"
  lastrecsql = "SELECT MAX(endtime) FROM recordedprogram"

  # execute SQL statement
  cursor.execute(nextrecsql)
  # get the time of next recording
  nextrec = cursor.fetchone()

  # get the end time of last recorded program
  # (will use to check if backend is currently recording)
  # We'll use this if the mythshutdown status check doesn't work
  cursor.execute(lastrecsql)
  lastrec = cursor.fetchone()


  db.close()
  del db
  del cursor
  global nextdt
  global lastdt
  global nexttitle
  nextdt, nexttitle=nextrec  
  lastdt=lastrec[0]
  timetonextrec = nextdt - datetime.now()
  MinsToNextRec = GetTimedeltaSeconds(timetonextrec) / 60
  if MinsToNextRec < minshutdown:
    global errorMessage
    errorMessage += "Next recording less than " + str(minshutdown) + " minutes (" + str(MinsToNextRec) + "). Exiting..."
    global fail
    fail=True
    if cronMode:
      printError(errorMessage)

def GetTimedeltaSeconds(myTimedelta):
  #Make sure we catch any increment greater than 24 hours
  mySeconds = ((myTimedelta.days) * 86400) + (myTimedelta.seconds)
  return mySeconds 

def checkCurrentRecording(lastrec):
  # if mythshutdown is not available then the method below can be used to detect current recordings  
  #if the end time of the last recorded program is later than the current time
  #the MythTV must be recording. We don't want the machine to suspend!
  if lastrec>datetime.now():
    global errorMessage
    errorMessage += "MythTV backend is currently recording. Exiting..."
    global fail
    fail=True
    if cronMode:
      printError(errorMessage)

def checkBackendStatus():
  mythStatusA=subprocess.Popen(statusscript, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
  mythStatusCode=int(mythStatusA.stdout.read())
  # Use the MythStatus class to process the code
  # If it's idle or less than 15 mins to next rec (which we ignore as we've got our own user variable) then we're good to go
  global mythBackend
  mythBackend = MythStatus.MythStatus(mythStatusCode)
  if not (mythBackend.IsIdle or mythStatusCode == 128):
    global errorMessage
    errorMessage += str(mythBackend)
    global fail
    fail=True
    if cronMode:
      printError(errorMessage)      

def checkCurrentPlayers():
  #if XBMC has any active players then we don't want to suspend
  #and we don't want any notifications. Script should be silent in background.
  getPlayers = json.loads(xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "Player.GetActivePlayers", "id": 1}'))
  if bool(getPlayers['result']['audio'])==True:
    global fail
    fail=True
  if bool(getPlayers['result']['picture'])==True:
    global fail
    fail=True  
  if bool(getPlayers['result']['video'])==True:
    global fail
    fail=True
  if fail:
    global errorMessage
    errorMessage += "Current player found. Exiting..."
    if cronMode:
      printError(errorMessage)

def checkCurrentSessions(sessions):
  #if we've got any active sessions e.g. www, ssh etc then we don't want to suspend.
  sessiontype=sessions.split(",")
  for s in sessiontype:
    sessionsearch="netstat -t |grep "
    sessionsearch+=s
    testsession = subprocess.Popen(sessionsearch, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    sessionresult=testsession.stdout.read()
    if bool(sessionresult):
      global errorMessage
      errorMessage += "Active session found (" + s + "). Exiting..."
      global fail
      fail=True
      if cronMode:
        printError(errorMessage)
      break

def calculateIncrement(nextRecordingTime):
  increment=nextRecordingTime-datetime.now()
  mywaketime=GetTimedeltaSeconds(increment) - boottime
  return mywaketime

def calculateUTC(nextRecordingTime):
  utctime = time.mktime(nextRecordingTime.timetuple()) 
  utcalarm = int(utctime) - int(boottime)
  return utcalarm

def setAlarm(nextRecordingTime):
  buildalarm="sudo " + alarmscript + " "
  if alarmtype == 1:
    buildalarm += "+" + str(calculateIncrement(nextRecordingTime))
  elif alarmtype == 0:
    buildalarm += str(calculateUTC(nextRecordingTime))  
  alarmresult = subprocess.Popen(buildalarm, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
  return

def doPowerDown():
  if actiontype == 0:
    print "Suspending..."
    setAlarm(nextdt)
    #xbmc.executebuiltin('XBMC.AlarmClock(mythalarm,Suspend,0.5,true)')
    xbmc.executebuiltin('Suspend')
  elif actiontype == 1:
    print "Hibernating..."
    setAlarm(nextdt)
    xbmc.executebuiltin('Hibernate')


def doAbort():
  global abort
  abort.update(100,"Powerdown aborted")
  time.sleep(1)
  abort.close()  

def doUnlock(unlock):
  if unlock:
    unlockcommand = "mythshutdown -u"
  else:
    unlockcommand = "mythshutdown -l"
  
  unlockbackend = subprocess.Popen(unlockcommand, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
  
def printError(message):
  print message
  
def getRecordingDetails():
  global nexttitle
  global nextdt
  if datetime.date(nextdt) == datetime.date(datetime.today()):
    recDay = "Today"
  else:
    recDay = nextdt.strftime("%A")
  recTime = nextdt.strftime("%H:%M")
  recordingDetails = nexttitle + " (" + recDay + " " + recTime + ")"
  return recordingDetails
  
def showUserDialog():
  userDialog=xbmcgui.Dialog()
  mythArgs=[]
  if not fail:
    mythArgs.append(actionfunction[actiontype])
    dialogTitle = "Next recording: " + getRecordingDetails()
  else:
    global errorMessage
    dialogTitle = errorMessage
    
  global mythBackend
  if mythBackend.IsLocked:
    mythArgs.append("Unlock")
  else:
    mythArgs.append("Lock")
  mythArgs.append("Settings")
  mythArgs.append("Cancel")


  userChoice=userDialog.select(dialogTitle, mythArgs)
  
  if mythArgs[userChoice] == "Settings":
    _A_.openSettings()
  if mythArgs[userChoice] == "Lock":
    doUnlock(False)
  if mythArgs[userChoice] == "Unlock":
    doUnlock(True)
  if mythArgs[userChoice] == "Suspend":
    doPowerDown()
  if mythArgs[userChoice] == "Hibernate":
    doPowerDown()
    

def ShowCountdown(duration):
  i=0
  global abort
  abort.create("MythTV Suspend Alarm", "Preparing to suspend...")
  while (i<duration and not abort.iscanceled()):  
    global abort    
    elapse=i
    percent = (i * 100) / duration
    countdown = duration - i
    countdowntext="Suspending in " + str(countdown) + " second(s)"
    abort.update(int(percent), countdowntext)
    time.sleep(1)
    i += 1
  if abort.iscanceled():
    print "MythSuspendAlarm: Process aborted by user."
    doAbort()
  else:
    print "MythSuspendAlarm: Beginning shutdown."
    global abort
    abort.close()
    doPowerDown()

# Right let's get cracking...

print "MythSuspendAlarm: Starting tests..."

# mythshutdown gives us a neat way to check backend status
# e.g recording, user jobs, etc
# This needs to be done first as we need to check if backend is locked
# Disable this if mythshutdown doesn't work
if not fail:
  checkBackendStatus()

# get the time of the next recording
if not fail:
  getMythTimes()

# Enable this if mythshutdown doesn't work
#checkCurrentRecording(lastdt)

if not fail:
  checkCurrentPlayers()

if not fail:
  checkCurrentSessions(sessiontypes)    

if not cronMode:
  showUserDialog()
  
if (cronMode and not fail):
  ShowCountdown(aborttime)





