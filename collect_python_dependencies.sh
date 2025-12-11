#!/bin/bash
# Run on mcx-rtos image (or virtualbox of) connected to internet, generates a tar.gz file
#
# To install python modules (collected inside the generated tar.gz) on another system:
#   tar xzpf dependencies.XXXXXXXXXX.tar.gz
#   pip3 install --no-index --find-links . -r requirements.txt
#
# Can also be used in "makedeb.sh" by unzipping dependencies.XXXXXXXXXX.tar.gz to "VENV_REQ_DIR"


Deps="motorcortex-python motorcortex-python-tools"
DepsLatest="plotly pandas numpy scipy pandas typing_extensions motorcortex-robot-control-python"

TgtDir=$(pwd)
TmpDir=$(mktemp -d)
python3 -m venv --system-site-packages ${TmpDir}
cd ${TmpDir}
. bin/activate
pip3 freeze > freeze0.txt
pip3 install ${Deps}
pip3 install --ignore-installed --upgrade ${DepsLatest}
pip3 freeze > freeze1.txt
mkdir download; cd download
comm -13 <(sort ../freeze0.txt) <(sort ../freeze1.txt) > requirements.txt
pip3 download -r requirements.txt
tar cvpzf $(mktemp -u -p ${TgtDir} --suffix .tar.gz dependencies.XXXXXXXXXX) .
cd ${TgtDir}
deactivate
rm -rf ${TmpDir}
