# Basic Python Plugin Example
#
# Author: Teubize
#
"""
<plugin key="HiKumo" name="Hitachi Airconditioning Hi-Kumo" author="teubize" version="1.0.0" externallink="">
    <params>
        <param field="Username" label="Email" width="200px" required="true" default=""/>
        <param field="Password" label="Password" width="200px" required="true" default=""/>
        <param field="Mode1" label="Update every x seconds" width="75px">
            <options>
                <option label="30" value="3" />
                <option label="60" value="6" default="true" />
                <option label="90" value="9" />
                <option label="120" value="12" />
                <option label="150" value="15" />
                <option label="180" value="18" />
                <option label="210" value="21" />
                <option label="240" value="24" />
            </options>
        </param>
        <param field="Mode2" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
        
    </params>
</plugin>
"""
import Domoticz
import requests
import json
import time

class BasePlugin:
    enabled = True
    powerOn = 0
    runCounter = 0
    config = None
    hiKumo = None
    
    def __init__(self):
        #self.var = 123
        return

    def onStart(self):
        Domoticz.Log("onStart called")

        if Parameters["Mode2"] == "Debug":
            Domoticz.Debugging(1)
            
        if (len(Devices) == 0):
            Domoticz.Device(Name="Power", Unit=1, Image=16, TypeName="Switch", Used=1).Create()
            Domoticz.Device(Name="Temp IN", Unit=2, TypeName="Temperature", Used=1).Create()
            Domoticz.Device(Name="Temp OUT", Unit=3, TypeName="Temperature",Used=1).Create()

            Options = {"LevelActions" : "||||||||",
                       "LevelNames" : "|Auto|AutoCool|AutoHeat|Cool|Heat|Circulator|Dry|Fan",
                       "LevelOffHidden" : "true",
                       "SelectorStyle" : "1"}
            
            Domoticz.Device(Name="Mode", Unit=4, TypeName="Selector Switch", Image=16, Options=Options, Used=1).Create()
            
            Options = {"LevelActions" : "|||||",
                       "LevelNames" : "|Auto|Silent|High|Low|Medium",
                       "LevelOffHidden" : "true",
                       "SelectorStyle" : "1"}
            
            Domoticz.Device(Name="Fan Rate", Unit=5, TypeName="Selector Switch", Image=7, Options=Options, Used=1).Create()
            Domoticz.Device(Name="Temp TARGET", Unit=6, Type=242, Subtype=1, Image=16, Used=1).Create()
            
            Domoticz.Log("Device created.")
        
        DumpConfigToLog()
        Domoticz.Heartbeat(10)
        
        self.config = Config(Parameters)
        
        self.hiKumo = HiKumoAdapter(self.config)

        Domoticz.Debug("utilisateur : " + self.hiKumo.config.api_username)
        Domoticz.Debug("Passe : " + self.hiKumo.config.api_password)

        data =self.hiKumo.login()
        if data["exec"] == "ok": data = self.hiKumo.fetch_api_setup_data()
        if data["exec"] == "ok": self.buildDevice()
       
        self.runCounter = int(Parameters["Mode1"])
        
    def onStop(self):
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
            Domoticz.Debug("Connection successful")
            

    def onMessage(self, Connection, Data):
        Domoticz.Log("onMessage called")

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("Command received U="+str(Unit)+" C="+str(Command)+" L= "+str(Level)+" H= "+str(Hue))
        
        if (Unit == 1):
            if(Command == "On"):
                self.powerOn = 1
                Devices[1].Update(nValue = 1, sValue ="100") 
            else:
                self.powerOn = 0
                Devices[1].Update(nValue = 0, sValue ="0") 
            
            #Update state of all other devices
            Devices[4].Update(nValue = self.powerOn, sValue = Devices[4].sValue)
            Devices[5].Update(nValue = self.powerOn, sValue = Devices[5].sValue)
            Devices[6].Update(nValue = self.powerOn, sValue = Devices[6].sValue)
        
        if (Unit == 4):
            Devices[4].Update(nValue = self.powerOn, sValue = str(Level))
            
        if (Unit == 5):
            Devices[5].Update(nValue = self.powerOn, sValue = str(Level))
        
        if (Unit == 6):
            Devices[6].Update(nValue = self.powerOn, sValue = str(Level))
            
        self.buildConfig()
        data = self.hiKumo.apply_api_config()
        if data["exec"] == "ok": self.buildDevice()
        
    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Debug("Connection " + Connection.Name + " closed.")

    def onHeartbeat(self):
        self.runCounter = self.runCounter - 1
        if self.runCounter <= 0:
            Domoticz.Debug("Poll unit")
            self.runCounter = int(Parameters["Mode1"])
            data = self.hiKumo.fetch_api_setup_data()
            if data["exec"] == "ok": self.buildDevice()
        else:
            Domoticz.Debug("Polling unit in " + str(self.runCounter) + " heartbeats.")

    def buildConfig(self):
        #power
        if (Devices[1].nValue == 1):
            self.powerOn = 1
            self.config.state = "on"
        else:
            self.powerOn = 0
            self.config.state = "off"
        #mode
        if (Devices[4].sValue == "10"):
            self.config.mode = "auto"
        elif (Devices[4].sValue == "20"):
            self.config.mode = "autoCooling"
        elif (Devices[4].sValue == "30"):
            self.config.mode = "autoHeating"
        elif (Devices[4].sValue == "40"):
            self.config.mode = "cooling"
        elif (Devices[4].sValue == "50"):
            self.config.mode = "heating"
        elif (Devices[4].sValue == "60"):
            self.config.mode = "circulator"
        elif (Devices[4].sValue == "70"):
            self.config.mode = "dehumidify"
        elif (Devices[4].sValue == "80"):
            self.config.mode = "fan"
            
        #fan
        if (Devices[5].sValue == "10"):
            self.config.fan = "auto"
        elif (Devices[5].sValue == "20"):
            self.config.fan = "silent"
        elif (Devices[5].sValue == "30"):
            self.config.fan = "high"
        elif (Devices[5].sValue == "40"):
            self.config.fan = "low"
        elif (Devices[5].sValue == "50"):
            self.config.fan = "medium"
            
        #target
        self.config.target = int(round(float(Devices[6].sValue)))
    
    def buildDevice(self):
        # Power
            if (self.config.state == "off"):
                if (Devices[1].nValue != 0):
                    Devices[1].Update(nValue = 0, sValue ="0") 
            else: 
                if (Devices[1].nValue != 1):
                    Devices[1].Update(nValue = 1, sValue ="100") 
             
            # Mode
            if (self.config.mode == "auto"):
                sValueNew = "10" 
            elif (self.config.mode == "heating"):
                sValueNew = "50" 
            elif (self.config.mode == "autoCooling"):
                sValueNew = "20" 
            elif (self.config.mode == "autoHeating"):
                sValueNew = "30" 
            elif (self.config.mode == "cooling"):
                sValueNew = "40" 
            elif (self.config.mode == "circulator"):
                sValueNew = "60"
            elif (self.config.mode == "dehumidify"):
                sValueNew = "70"
            elif (self.config.mode == "fan"):
                sValueNew = "80"
                
            if (Devices[4].nValue != self.powerOn or Devices[4].sValue != sValueNew):
                Devices[4].Update(nValue = self.powerOn, sValue = sValueNew)
         
            # Fan rate
            if (self.config.fan == "auto"):
                sValueNew = "10" 
            elif (self.config.fan == "silent"):
                sValueNew = "20" 
            elif (self.config.fan == "high"):
                sValueNew = "30"
            elif (self.config.fan == "low"):
                sValueNew = "40" 
            elif (self.config.fan == "medium"):
                sValueNew = "50"
                
            if (Devices[5].nValue != self.powerOn or Devices[5].sValue != sValueNew):
                Devices[5].Update(nValue = self.powerOn, sValue = sValueNew)
                
            # Setpoint temperature
            if (Devices[6].nValue != self.powerOn or (Devices[6].sValue != str(self.config.target))):
                Devices[6].Update(nValue = self.powerOn, sValue =  str(self.config.target))
                
            Devices[2].Update(nValue = 0, sValue = str(self.config.indoor))
            Devices[3].Update(nValue = 0, sValue = str(self.config.outdoor))
            
global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

    # Generic helper functions
def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

################

class Config:
    api_url= "https://ha117-1.overkiz.com/enduser-mobile-web/enduserAPI"
    api_user_agent = "HiKumoPluginDomoticz"
    api_username = None
    api_password = None
    mode = "heating"
    state = "on"
    target = 18
    indoor = 0
    outdoor = 0
    fan = "silent"
    climUrl = None
	   
    def __init__(self, raw):
        self.api_username = raw["Username"]
        self.api_password = raw["Password"]
        self.api_url = raw.get("api_url", self.api_url)
        self.api_user_agent = raw.get("api_user_agent", self.api_user_agent)
    
############################################

class HiKumoAdapter:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()

    def get_api(self, url, data, headers, retry=1):
        try:
            response = self.session.get(url=url, headers=headers, data=data)
        except Exception as e:
            Domoticz.Debug(e)
            response = None

        if response is None:
            status_code = -1
        else:
            status_code = response.status_code

        if status_code != 200:
            if retry > 0:
                Domoticz.Debug("API call failed with status code " + str(status_code) +". Retrying.")
                time.sleep(1)
                self.login()
                return self.get_api(url, data, headers, retry - 1)
            else:
                Domoticz.Debug("API call failed with status code " + str(status_code) +". No more retry.")
                return None
        else:
            return response

    def post_api(self, url, data, headers, retry=1):
        try:
            response = self.session.post(url=url, headers=headers,data = data)
        except Exception as e:
            Domoticz.Debug(e)
            response = None

        if response is None:
            status_code = -1
        else:
            status_code = response.status_code

        if status_code != 200:
            if retry > 0:
                Domoticz.Debug("API call failed with status code " + str(status_code) +". Retrying.")
                time.sleep(2)
                self.login()
                return self.post_api(url, data, headers, retry - 1)
            else:
                Domoticz.Debug("API call failed with status code " + str(status_code) +". No more retry.")
                return None
        else:
            return response

    def login(self):
        url = self.config.api_url + "/login"
        data = {'userId': self.config.api_username, 'userPassword': self.config.api_password}
        headers = {'user-agent': self.config.api_user_agent, 'content-type': 'application/x-www-form-urlencoded; charset=UTF-8'}
        try:
            response = self.session.post(url, data=data, headers=headers, timeout=(5, 10))
            if response is None:
                status_code = -1
            else:
                status_code = response.status_code
            if status_code != 200:
                Domoticz.Debug(response.text)
                Domoticz.Log("NOT Logged into Hi-Kumo !!!")
                return {'exec': 'error'}
            else:
                Domoticz.Log("NOT Logged into Hi-Kumo !!!")
                return {'exec': 'ok'}
        except Exception as e:
            Domoticz.Debug(e)
            return {'exec': 'error'}

    def fetch_api_setup_data(self):
        url = self.config.api_url + "/setup"
        data = {}
        headers = {'user-agent': self.config.api_user_agent, 'Content-Type': 'application/json'}
        response = self.get_api(url, data, headers, 1)
        if response is None:
            return {'exec': 'error'}
        else:
            data = json.loads(response.text)
            for value in data["devices"]:
                if value["controllableName"] == "hlrrwifi:HLinkMainController":
                    self.config.climUrl = value["deviceURL"]
                    for value2 in value["states"]:
                        if value2["name"] == "hlrrwifi:MainOperationState":			
                            self.config.state = value2["value"] 
                        if value2["name"] == "hlrrwifi:ModeChangeState":			
                            self.config.mode =  value2["value"]
                        if value2["name"] == "hlrrwifi:FanSpeedState":			
                            self.config.fan =  value2["value"]
                        if value2["name"] == "hlrrwifi:RoomTemperatureState":
                            self.config.indoor = value2["value"]
                        if value2["name"] == "hlrrwifi:OutdoorTemperatureState":
                            self.config.outdoor = str(value2["value"])
                        if value2["name"] == "hlrrwifi:TemperatureChangeState":			
                            self.config.target =  value2["value"]
            return {'exec': 'ok'}

    def apply_api_config(self):
        url = self.config.api_url + "/exec/apply"
        tmpTarget = self.config.target
        tmpState = self.config.state
        tmpFan = self.config.fan
        tmpMode = self.config.mode
        i = 0
        data =  "{\"label\" : \"Room focus : set air to air heat pump state\" ,\r\n \"actions\" : [{ \"deviceURL\" : \"%s\" ,\r\n\"commands\" : [{ \"name\" : \"globalControl\" ,\r\n \"parameters\" : [ \"%s\" ,  %d ,  \"%s\" ,  \"%s\" ,  \"stop\" ,  \"off\" ] }]}] }"% (self.config.climUrl,self.config.state,self.config.target,self.config.fan,self.config.mode)
        headers = {'user-agent': self.config.api_user_agent, 'Content-Type': 'application/json'}
        response = self.post_api(url, data, headers)       
        if response is None:
            return {'exec': 'error'}
        else:
            data = json.loads(response.text)
            for key, value in data.items():
                if key == "execId":
                    while True:					
                        tmpChange = True
                        i = i + 1
                        time.sleep(1)
                        self.fetch_api_setup_data()
                        if tmpTarget != self.config.target: tmpChange = False
                        if tmpState != self.config.state: tmpChange = False
                        if tmpFan != self.config.fan: tmpChange = False
                        if tmpMode != self.config.mode: tmpChange = False
                        if tmpChange == True: return {'exec': 'ok'}
                        if i >= 20: return {'exec': 'timeout'}
            return {'exec': 'error'}


############################################

