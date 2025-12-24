# import the motorcortex library
import motorcortex
import time

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
    
reply = req.setParameter("root/Logic/stateCommand", 2).get()
print(f"Open: {reply}")

import time 
for i in range(5):
    reply = req.setParameter("root/UserParameters/IO/gripper", 0).get()
    time.sleep(1)
    reply = req.setParameter("root/UserParameters/IO/gripper", 1).get()
    time.sleep(1)


reply = req.setParameter("root/Logic/modeCommand", 3).get()
print(f"Set to manual joint mode: {reply}")
time.sleep(2)
reply = req.setParameter("root/ManipulatorControl/hostInJointVelocity", [0.1, 0.3, 0.0, 0.0, 0.0, 0.3]).get()
print(f"Set joint velocity: {reply}")

reply = req.setParameter("root/Logic/modeCommand", 3).get()
print(f"Set to manual joint mode: {reply}")
time.sleep(2)
reply = req.setParameter("root/ManipulatorControl/hostInJointVelocity", [0.1, 0.3], offset=2, length=2).get()
print(f"Set joint velocity: {reply}")

reply = req.overwriteParameter("root/ManipulatorControl/hostInJointVelocityGain", 0.0, force_activate=True).get()
print(f"Set joint position: {reply}")
time.sleep(5)
reply = req.releaseParameter("root/ManipulatorControl/hostInJointVelocityGain").get()