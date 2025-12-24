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
  print(f"Parameters: {tree}")
except RuntimeError as err:
    print(err)