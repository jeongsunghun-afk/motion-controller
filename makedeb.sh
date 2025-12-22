#!/bin/bash

# Set variables
PACKAGE_NAME="datalogger"
VERSION="1.0"
ARCHITECTURE="all"
MAINTAINER="Vectioneer B.V. <info@vectioneer.com>"
DESCRIPTION="A client application for getting and setting data in a Motorcortex Control Application"
PYTHON_SCRIPT="datalogger.py"
PYTHON_MODULES="src" # directories, space separated list
SERVICE="${PACKAGE_NAME}"
BUILDFOLDER="build"

VENV_REQ_DIR="venv-req"
VENV_TARGET_DIR="/usr/local/.venv.${PACKAGE_NAME}"

# Remove existing build folder if it exists
if [ -d "${BUILDFOLDER}" ]; then
    echo "Removing existing build folder..."
    rm -rf ${BUILDFOLDER}
fi

# Create package directory structure
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/systemd/system
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}${VENV_TARGET_DIR}

# Create control file
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/control << EOF
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Architecture: ${ARCHITECTURE}
Maintainer: ${MAINTAINER}
Description: ${DESCRIPTION}
EOF

# Create preinst file
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/preinst << EOF
python3 -m venv --clear --system-site-packages ${VENV_TARGET_DIR}
EOF

# Create postinst file
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/postinst << EOF
if [ -d "${VENV_TARGET_DIR}/${VENV_REQ_DIR}" ]; then
    source ${VENV_TARGET_DIR}/bin/activate 
    pip3 install --no-index --find-links ${VENV_TARGET_DIR}/${VENV_REQ_DIR} -r ${VENV_TARGET_DIR}/${VENV_REQ_DIR}/requirements.txt > /dev/null
    deactivate
    rm -rf ${VENV_TARGET_DIR}/${VENV_REQ_DIR}
fi
systemctl daemon-reload
systemctl enable ${SERVICE}
systemctl start ${SERVICE}
EOF

# Create prerm file
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/prerm << EOF
rm -rf ${VENV_TARGET_DIR}
systemctl stop ${SERVICE}
systemctl disable ${SERVICE}
EOF

# Create postrm file
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/postrm << EOF
EOF

# Copy the venv requirements dir
if [ -d "${VENV_REQ_DIR}" ]; then
    cp -a ${VENV_REQ_DIR} ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}${VENV_TARGET_DIR}/
fi

# Copy python scripts
cp -a ${PYTHON_SCRIPT} ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}${VENV_TARGET_DIR}/
for MOD in ${PYTHON_MODULES}; do
    if [ -d "${MOD}" ]; then
        cp -ar ${MOD} ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}${VENV_TARGET_DIR}/
    else
        echo "Module/directory ${MOD} not found, skipping..."
    fi
done

# Copy the service file and replace start command
cp template.service.in ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/systemd/system/${SERVICE}.service
sed -i "s|@EXEC_START@|/bin/bash -c 'source ${VENV_TARGET_DIR}/bin/activate \&\& CONFIG_PATH="/etc/motorcortex/config/services/${PACKAGE_NAME}.json" python3 ${VENV_TARGET_DIR}/${PYTHON_SCRIPT}; deactivate'|g" ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/systemd/system/${SERVICE}.service

# Set executable permissions
chmod -f +x ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/{preinst,postinst,prerm,postrm}

# Build the package
dpkg-deb -Zxz --build ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}

echo "Debian package created: ${PACKAGE_NAME}_${VERSION}.deb"
