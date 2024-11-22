# mcx-client-app-template


## Description
This python project is an example for creating a motorcortex client application in python and distributing it as a Debian package, that can be deployed via the motorcortex portal (https://motorcortex.io/).

## Structure of the project
The project contains the following files:
- mcx-client-app.py: the template for the python client app that already has the structure so it can be started and stopped from a set of motorcortex user parameters that in turn can easily be set from a GRID GUI widget.

- mcx-client-app.service: the systemd service script that registers the script as a service, so it automatically starts when the motorcortex server app is started.

- makedeb.sh: a script that generates a debain package that is compatible with MCX-RTOS. You may modify the contents of this script to change the package name, description, version and dependencies. Running this scrip creates a build folder where all Debian control files are created and the deb package is created. 

- mcx.cert.crt: for convenience the default motorcortex security certificate is added to the project in case you want to test the script from your local computer. When you deploy the script as a debian to an MCX-RTOS image, refer to the default certificate instead: /etc/ssl/certs/mcx.cert.pem
