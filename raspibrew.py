#
# Copyright (c) 2012 Stephen P. Smith
#
# Permission is hereby granted, free of charge, to any person obtaining 
# a copy of this software and associated documentation files 
# (the "Software"), to deal in the Software without restriction, 
# including without limitation the rights to use, copy, modify, 
# merge, publish, distribute, sublicense, and/or sell copies of the Software, 
# and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included 
# in all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS 
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR 
# IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


from multiprocessing import Process, Pipe, current_process
from subprocess import Popen, PIPE, call
from datetime import datetime
import web, time, random, json
#uncomment for raspberry pi
from smbus import SMBus
from pid import pid as PIDController


urls = ("/", "raspibrew",
        "/getrand", "getrand",
        "/getstatus", "getstatus")

render = web.template.render("templates/")

app = web.application(urls, globals())

global parent_conn, runonce
runonce = True

class raspibrew: 
    def __init__(self):
        
        global parent_conn, runonce
        
        self.mode = "off"
        self.cycle_time = 2.0
        self.duty_cycle = 0.0
        self.set_point = 0.0
        self.k_param = 2.39
        self.i_param = 489
        self.d_param = 44.9
        
        if runonce:
            parent_conn, child_conn = Pipe()       
            #rename to tempControlProc to test with raspberry pi    
            p = Process(name = "tempControlProc", target=tempControlProc, args=(self.mode, self.cycle_time, self.duty_cycle, \
                                                          self.set_point, self.k_param, self.i_param, self.d_param, \
                                                          child_conn))
            p.start()
            runonce = False

    def GET(self):
       
        return render.raspibrew(self.mode, self.set_point, self.duty_cycle, self.cycle_time, \
                                self.k_param,self.i_param,self.d_param)
        
    def POST(self):
        global parent_conn
        data = web.data()
        #print data
        datalist = data.split("&")
        for item in datalist:
            datalistkey = item.split("=")
            if datalistkey[0] == "mode":
                self.mode = datalistkey[1]
            if datalistkey[0] == "setpoint":
                self.set_point = float(datalistkey[1])
            if datalistkey[0] == "dutycycle":
                self.duty_cycle = float(datalistkey[1])
            if datalistkey[0] == "cycletime":
                self.cycle_time = float(datalistkey[1])
            if datalistkey[0] == "p":
                self.k_param = float(datalistkey[1])
            if datalistkey[0] == "i":
                self.i_param = float(datalistkey[1])
            if datalistkey[0] == "d":
                self.d_param = float(datalistkey[1])
            
        parent_conn.send([self.mode, self.cycle_time, self.duty_cycle, self.set_point, \
                              self.k_param, self.i_param, self.d_param])  
             
            #mode, cycle_time, duty_cycle = parent_conn.recv()
            
            #print mode
            #print cycle_time
            #print duty_cycle
               
        #return render.raspibrew(self.mode,self.set_point, self.duty_cycle, self.cycle_time, \
        #                        self.k_param,self.i_param,self.d_param)
 
def getrandProc(conn):
    p = current_process()
    print 'Starting:', p.name, p.pid
    while (True):
        #t = time.time()
        num = randomnum()
        #elapsed = time.time() - t
        time.sleep(.5) 
        #print num
        conn.send(num)

        
def gettempProc(conn):
    p = current_process()
    print 'Starting:', p.name, p.pid
    while (True):
        #t = time.time()
        num = tempdata()
        #elapsed = time.time() - t
        time.sleep(.05) #.5+~.83 = ~1.33 seconds
        conn.send(num)

def getonofftime(cycle_time, duty_cycle):
    duty = duty_cycle/100.0
    on_time = cycle_time*(duty)
    off_time = cycle_time*(1.0-duty)   
    return [on_time, off_time]
        
def heatProctest(cycle_time, duty_cycle, conn):
    #p = current_process()
    #print 'Starting:', p.name, p.pid
    while (True):
        if (conn.poll()):
            cycle_time, duty_cycle = conn.recv()
            
        on_time, off_time = getonofftime(cycle_time, duty_cycle)
        #print on_time
        # led on
        time.sleep(on_time)
        #print off_time
        # led off
        time.sleep(off_time)
        conn.send([cycle_time, duty_cycle]) #shows its alive
        
        
def heatProc(cycle_time, duty_cycle, conn):
    p = current_process()
    print 'Starting:', p.name, p.pid
    bus = SMBus(0)
    bus.write_byte_data(0x20,0x00,0x00) #set I/0 to write
    while (True):
        while (conn.poll()): #get last
            cycle_time, duty_cycle = conn.recv()
        conn.send([cycle_time, duty_cycle])    
        if duty_cycle == 0:
            bus.write_byte_data(0x20,0x09,0x00)
            time.sleep(cycle_time)
        elif duty_cycle == 100:
            bus.write_byte_data(0x20,0x09,0x01)
            time.sleep(cycle_time)
        else:
            on_time, off_time = getonofftime(cycle_time, duty_cycle)
            bus.write_byte_data(0x20,0x09,0x01)
            time.sleep(on_time)
            bus.write_byte_data(0x20,0x09,0x00)
            time.sleep(off_time)
        
        #y = datetime.now()
        #time_sec = y.second + y.microsecond/1000000.0
        #print "%s Thread time (sec) after LED off: %.2f" % (self.getName(), time_sec)

def tempControlProcTest(mode, cycle_time, duty_cycle, set_point, k_param, i_param, d_param, conn):
    
        p = current_process()
        print 'Starting:', p.name, p.pid
        parent_conn_temp, child_conn_temp = Pipe()            
        ptemp = Process(name = "getrandProc", target=getrandProc, args=(child_conn_temp,))
        #ptemp.daemon = True
        ptemp.start()   
        parent_conn_heat, child_conn_heat = Pipe()           
        pheat = Process(name = "heatProctest", target=heatProctest, args=(cycle_time, duty_cycle, child_conn_heat))
        #pheat.daemon = True
        pheat.start()  
        
        while (True):
            if parent_conn_temp.poll():
                randnum = parent_conn_temp.recv() #non blocking receive
                conn.send([randnum, mode, cycle_time, duty_cycle, set_point, k_param, i_param, d_param])
            if parent_conn_heat.poll():
                cycle_time, duty_cycle = parent_conn_heat.recv()
                #duty_cycle = on_time/offtime*100.0
                #cycle_time = on_time + off_time
            if conn.poll():
                mode, cycle_time, duty_cycle, set_point, k_param, i_param, d_param = conn.recv()
                #conn.send([mode, cycle_time, duty_cycle])
                #if mode == "manual": 
                parent_conn_heat.send([cycle_time, duty_cycle])
            
#controls 

def tempControlProc(mode, cycle_time, duty_cycle, set_point, k_param, i_param, d_param, conn):
    
        p = current_process()
        print 'Starting:', p.name, p.pid
        parent_conn_temp, child_conn_temp = Pipe()            
        ptemp = Process(name = "gettempProc", target=gettempProc, args=(child_conn_temp,))
        ptemp.daemon = True
        ptemp.start()   
        parent_conn_heat, child_conn_heat = Pipe()           
        pheat = Process(name = "heatProc", target=heatProc, args=(cycle_time, duty_cycle, child_conn_heat))
        pheat.daemon = True
        pheat.start()  
        
        while (True):
            readytemp = False
            while parent_conn_temp.poll():
                temp = parent_conn_temp.recv() #non blocking receive    
                readytemp = True
            if readytemp == True:
                conn.send([temp, mode, cycle_time, duty_cycle, set_point, k_param, i_param, d_param]) #GET request
                readytemp == False
            readyheat = False    
            while parent_conn_heat.poll(): #non blocking receive
                cycle_time, duty_cycle = parent_conn_heat.recv()
                readyheat = True
            if readyheat == True:
                if mode == "auto":
                    #calculate PID every cycle
                    duty_cycle = pid.calcPID(float(temp), float(set_point), 1)
                    #send to heat process every cycle
                    parent_conn_heat.send([cycle_time, duty_cycle])     
                    readyheat = False     
            readyPOST = False
            while conn.poll(): #POST settings
                mode, cycle_time, duty_cycle_temp, set_point, k_param, i_param, d_param = conn.recv()
                readyPOST = True
            if readyPOST == True:
                if mode == "auto":
                    print "auto selected"
                    pid = PIDController.PID(cycle_time, k_param, i_param, d_param) #init pid
                    duty_cycle = pid.calcPID(float(temp), float(set_point), 1)
                    parent_conn_heat.send([cycle_time, duty_cycle])  
                if mode == "manual": 
                    print "manual selected"
                    duty_cycle = duty_cycle_temp
                    parent_conn_heat.send([cycle_time, duty_cycle])    
                if mode == "off":
                    print "off selected"
                    duty_cycle = 0
                    parent_conn_heat.send([cycle_time, duty_cycle])
                readyPOST = False
            time.sleep(.01)
                    
class getrand:
    def __init__(self):
        pass
    def GET(self):
        global parent_conn  
        randnum, mode, cycle_time, duty_cycle, set_point, k_param, i_param, d_param = parent_conn.recv()
        #controlData = parent_conn.recv()
        out = json.dumps({"temp" : randnum,
                          "mode" : mode,
                    "cycle_time" : cycle_time,
                    "duty_cycle" : duty_cycle,
                     "set_point" : set_point,
                       "k_param" : k_param,
                       "i_param" : i_param,
                       "d_param" : d_param})  
        return out
        #return randomnum()
        
    def POST(self):
        pass

class getstatus:
    def __init__(self):
        pass    

    def GET(self):
        global parent_conn
        temp, mode, cycle_time, duty_cycle, set_point, k_param, i_param, d_param = parent_conn.recv()
        out = json.dumps({"temp" : temp,
                          "mode" : mode,
                    "cycle_time" : cycle_time,
                    "duty_cycle" : duty_cycle,
                     "set_point" : set_point,
                       "k_param" : k_param,
                       "i_param" : i_param,
                       "d_param" : d_param})  
        return out
        #return tempdata()
       
    def POST(self):
        pass
    
def randomnum():
    time.sleep(.5)
    return random.randint(50,220)

def tempdata():
    #change 28-000002b2fa07 to your own temp sensor id
    pipe = Popen(["cat","/sys/bus/w1/devices/w1_bus_master1/28-000002b2fa07/w1_slave"], stdout=PIPE)
    result = pipe.communicate()[0]
    result_list = result.split("=")
    temp_C = float(result_list[-1])/1000 # temp in Celcius
    temp_F = (9.0/5.0)*temp_C + 32
    return "%.2f" % temp_F

if __name__ == '__main__':
    
    #uncomment for raspberry pi
    call(["modprobe", "w1-gpio"])
    call(["modprobe", "i2c-dev"])
    app.run()


