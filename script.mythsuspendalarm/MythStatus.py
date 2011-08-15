class MythStatus:
  _statuscode=0
  _transcoding = False
  _comflagging = False
  _epg = False
  _locked = False
  _jobrunning = False
  _recording = False
  _dailywake = False
  _nearrecord = False
  _setup = False
  _idle = False
  _mylist = []
  
  def __init__(self, status):
    
    self._statuscode = status   
    
    if (status < 0 or status > 511):
      raise Exception("Invalid Status Code")
    
    else:
      if status == 0:
        self._idle = True
        self._mylist.append("Idle")
      if status >= 255:
        self._setup = True
        status -= 255
        self._mylist.append("Seting Up")
      if status >= 128:
        self._nearrecord = True
        status -= 128
        self._mylist.append("Near Next Record")        
      if status >= 64:
        self._dailywake = True
        status -= 64 
        self._mylist.append("In Daily Wake")        
      if status >= 32:
        self._jobrunning = True
        status -= 32
        self._mylist.append("Running Job")
      if status >= 16:
        self._locked = True
        status -= 16
        self._mylist.append("Locked")
      if status >= 8:
        self._recording = True
        status -= 8
        self._mylist.append("Recording")
      if status >= 4:
        self._epg = True
        status -= 4
        self._mylist.append("Getting EPG")
      if status >= 2:
        self._comflagging = True
        status -= 2
        self._mylist.append("Comflagging")
      if status >= 1:
        self._transcoding = True
        status -= 1
        self._mylist.append("Transcoding")

  def getidle(self):
    return self._idle
    
  def gettranscoding(self):
    return self._transcoding
    
  def getcomflagging(self):
    return self._comflagging
    
  def getepg(self):
    return self._epg
    
  def getlocked(self):
    return self._locked
    
  def getjob(self):
    return self._jobrunning
    
  def getrecord(self):
    return self._recording
    
  def getdailywake(self):
    return self._dailywake
    
  def getnearrecord(self):
    return self._nearrecord
    
  def getsetup(self):
    return self._setup
    
  def __str__(self):
    text = "(" + str(self._statuscode) + ") "
    for mythcode in self._mylist:
      text += mythcode + ", "
    return text[0:len(text)-2]
    
  IsIdle = property(getidle, None, None, None)
  
  IsTranscoding = property(gettranscoding, None, None, None)

  IsComflagging = property(getcomflagging, None, None, None)
  
  IsGettingEPG = property(getepg, None, None, None)
  
  IsLocked = property(getlocked, None, None, None)
  
  IsRecording = property(getrecord, None, None, None)
  
  IsRunningJob =  property(getjob, None, None, None) 

  IsInDailyWake = property(getdailywake, None, None, None)
  
  IsNearRecord = property(getnearrecord, None, None, None)
  
  IsInSetup = property(getsetup, None, None, None)

