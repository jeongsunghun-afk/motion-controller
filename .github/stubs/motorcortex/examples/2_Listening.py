# import the motorcortex library
import motorcortex

IP_ADDRESS = "wss://192.168.2.100:5568:5567"
PATH_TO_CERTIFICATE = "mcx.cert.crt"
LOGIN = "admin"
PASSWORD = "vectioneer"

# Create a parameter tree object
parameter_tree = motorcortex.ParameterTree()
# Open request and subscribe connection
try:
  req, sub = motorcortex.connect(IP_ADDRESS, motorcortex.MessageTypes(), parameter_tree,
                                   certificate=PATH_TO_CERTIFICATE, timeout_ms=300,
                                   login=LOGIN, password=PASSWORD)
  tree = parameter_tree.getParameterTree()
except RuntimeError as err:
    print(err)
    
import time

while True:
    # get the parameter value
    position = req.getParameter('root/ManipulatorControl/manipulatorToolPoseActual').get()
    if position is not None:
        print(f"EE Position: {position.value}")
    else:
        print("Failed to get parameter value")
    # wait for 1 second before requesting again
    time.sleep(1)

# define a callback function that will be called when new data is received
def print_value(result):
    print(f"Received new positions: {result[0].value}")
    
# Subscribe to parameter changes
sub_position = sub.subscribe('root/ManipulatorControl/manipulatorToolPoseActual', "Group1", frq_divider=100)

# get reply from the server
is_subscribed = sub_position.get()
# print subscription status and layout
if (is_subscribed is not None) and (is_subscribed.status == motorcortex.OK):
    print(f"Subscription successful, layout: {sub_position.layout()}")
else:
    print(f"Subscription failed")
    sub.close()
    exit()

# set the callback function that handles the received data
# Note that this is a non-blocking call, starting a new thread that handles
# the messages. You should keep the application alive for a s long as you need to
# receive the messages
sub_position.notify(print_value)

while True: # keep the application alive for testing the notify
    pass

import time

paths = ['root/ManipulatorControl/manipulatorToolPoseActual',
         'root/ManipulatorControl/jointPositionsActual']
sub_multi = sub.subscribe(paths, group_alias="Group1", frq_divider=1000)

is_subscribed = sub_multi.get()
# print subscription status and layout
if (is_subscribed is not None) and (is_subscribed.status == motorcortex.OK):
    print(f"Subscription successful, layout: {sub_multi.layout()}")
else:
    print(f"Subscription failed")
    sub.close()
    exit()

# set the callback function that handles the received data
def print_multi_value(result):
    print(f"Received new EE position: {result[0].value}, \nJoint positions: {result[1].value}\n\n")

sub_multi.notify(print_multi_value)

time.sleep(60)  # keep the application running for 60 seconds to receive updates
sub.close()  # close the subscription when done