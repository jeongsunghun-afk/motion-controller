#!/usr/bin/python3

#
#   Developer : Philippe Piatkiewitz (philippe.piatkiewitz@vectioneer.com)
#   All rights reserved. Copyright (c) 2024 VECTIONEER.
#

TARGETURL="wss://127.0.0.1:5568:5567"
#CERT = "/etc/ssl/certs/mcx.cert.pem"
CERT = "mcx.cert.crt"

START_PARAM = "root/UserParameters/GUI/ScriptIO/startscript"
STOP_PARAM = "root/UserParameters/GUI/ScriptIO/stopscript"
STATECMD_PARAM = "root/Logic/stateCommand"
STATE_PARAM = "root/Logic/state"

import motorcortex
import time
from math import pi

import operator
waitForOperators = {
    "==": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}

stateCommand = {
    "DO_NOTHING_E": -1,
    "GOTO_OFF_E": 0,
    "GOTO_IDLE_E": 1,
    "GOTO_ENGAGED_E": 2,
    "GOTO_REFERENCING_E": 4,
    "FORCE_IDLE_E": 10,
    "EMERGENCY_STOP_E": 20,
    "SAVE_CONFIGURATION": 254,
    "ACKNOWLEDGE_ERROR": 255
}

state = {
    "INIT_S": 0,
    "OFF_S": 1,
    "IDLE_S": 2,
    "PAUSED_S": 3,
    "ENGAGED_S": 4,
    "HOMING_S": 5,
    "FORCEDIDLE_S": 6,
    "ESTOP_OFF_S": 7,
    "OFF_TO_IDLE_T": 102,
    "OFF_TO_REFERENCING_T": 105,
    "IDLE_TO_OFF_T": 201,
    "PAUSED_TO_IDLE_T": 302,
    "IDLE_TO_ENGAGED_T": 204,
    "ENGAGED_TO_PAUSED_T": 403,
    "TO_FORCEDIDLE_T": 600,
    "RESET_FORCEDIDLE_T": 602,
    "TO_ESTOP_T": 700,
    "RESET_ESTOP_T": 701
}

STOP = False


class StopSignal(Exception):
    """Stop signal received"""
    pass

def waitFor(req, param, value=True, index=0, timeout=30, testinterval=0.2, operat="==", blockStopSignal=False):
    """Wait for a parameter to meet a certain condition, then continue or timeout, while testing for the STOP signal"""
    global STOP
    to=time.time()+timeout
    op_func = waitForOperators[operat]
    print("Waiting for " + param + " " + str(operat) + " " + str(value))
    while not op_func(req.getParameter(param).get().value[index], value):
        if (STOP and not blockStopSignal):
            print("STOP")
            raise StopSignal("Received stop signal")
        time.sleep(testinterval)
        if ((time.time()>to) and (timeout>0)):
            print("Timeout")
            return False
    return True

def wait(timeout=30, testinterval=0.2, blockStopSignal=False):
    """Wait for a timeout, while testing for the STOP signal"""
    global STOP
    to=time.time()+timeout
    while True:
        if (STOP and not blockStopSignal):
            print("STOP")
            raise StopSignal("Received stop signal")
        time.sleep(testinterval)
        if ((time.time()>to) and (timeout>0)):
            print("Timeout")
            return False
    return True

def stopCallback(msg):
    """Callback when receiving a message from the subscription"""
    global STOP
    if msg[0].value[0] == 1:
        STOP = True


def main(id):
    global TARGETURL
    global START_PARAM
    global STOP_PARAM
    global CERT
    global STOP
    # Creating empty object for parameter tree
    parameter_tree = motorcortex.ParameterTree()
    # Loading protobuf types and hashes
    motorcortex_types = motorcortex.MessageTypes()
    # Open request connection
    try:
      req, sub = motorcortex.connect(TARGETURL, motorcortex_types, parameter_tree, certificate=CERT, timeout_ms=10000,
                                     login="", password="")
    except:
      print("Failed to connect to %s. Exiting"%TARGETURL)
      exit(0)
    # Set the start parameter to zero on the server
    req.setParameter(START_PARAM, 0).get()
    req.setParameter(STOP_PARAM, 0).get()
    # use a subscription to listen for the stop parameter in a separate thread
    sub.subscribe(STOP_PARAM, "mcx-client-app", 100).notify(stopCallback)
    while (True):
        # Wait forever until the start parameter becomes true
        waitFor(req, START_PARAM, timeout=-1, blockStopSignal=True)
        # Command the system to engaged
        req.setParameter(STATECMD_PARAM, stateCommand["GOTO_ENGAGED_E"]).get()
        waitFor(req, STATE_PARAM, state["ENGAGED_S"], blockStopSignal=True)
        # a try is used to catch a stop signal, so the commands below can be interrupted Regularly check if the stop
        # signal is triggered to interrupt teh execution of the commands. In this example we use wait and waitFor that
        # check for the stop signal internally at regular intervals
        try:
            print("Sleeping...")
            wait(5)
            # Do your actions here
            # ...
        except StopSignal as err:
            # when stop condition is met, this code is executed
            print(err)
        except:
            # all other errors are not handled
            raise
        finally:
            # reset the commands
            req.setParameter(STOP_PARAM, 0).get()
            req.setParameter(START_PARAM, 0).get()
            # Reset the stop flag
            STOP = False
            # Switch the system Off
            req.setParameter(STATECMD_PARAM, stateCommand["GOTO_OFF_E"]).get()
            waitFor(req, STATE_PARAM,state["OFF_S"], blockStopSignal=True)
    req.close()
    sub.close()

if __name__ == '__main__':
    # creating thread
    main(1)

