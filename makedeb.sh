#!/bin/bash

# Set variables
PACKAGE_NAME="mcx-client-app"
VERSION="1.0"
ARCHITECTURE="all"
MAINTAINER="Vectioneer B.V. <info@vectioneer.com>"
DESCRIPTION="A client application for getting and setting data in a Motorcortex Control Application"
PYTHON_SCRIPT="mcx-client-app.py"
SERVICE="mcx-client-app"
BUILDFOLDER="build"

# Do not install the certificate, because we assume that this is already on the target system
#CERTIFICATE="mcx.cert.crt"


# Create package directory structure
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/usr/local/bin
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/motorcortex
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/systemd/system

# Create control file
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/control << EOF
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Architecture: ${ARCHITECTURE}
Maintainer: ${MAINTAINER}
Description: ${DESCRIPTION}
EOF

# Create postinst file
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/postinst << EOF
systemctl daemon-reload
systemctl enable ${SERVICE}
systemctl start ${SERVICE}
EOF

# Create postrm file
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/prerm << EOF
systemctl stop ${SERVICE}
systemctl disable ${SERVICE}
EOF


# Copy Source files
cp ${PYTHON_SCRIPT} ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/usr/local/bin/
#cp ${CERTIFICATE} ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/motorcortex/
cp ${SERVICE}.service ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/systemd/system/


# Set executable permissions
chmod +x ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/usr/local/bin/${PYTHON_SCRIPT}
chmod +x ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/postinst
chmod +x ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/prerm

# Build the package
dpkg-deb -Zxz --build ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}

echo "Debian package created: ${PACKAGE_NAME}_${VERSION}.deb"
