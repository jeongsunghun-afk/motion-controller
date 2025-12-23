#!/bin/bash


# Function to get value from JSON (first arg: key, second arg: json file)
get_json_value() {
    local key="$1"
    local file="$2"
    jq -r --arg key "$key" '.[$key] // empty' "$file"
}


# Determine config file to use
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_CONFIG="${SCRIPT_DIR}/default_service_config.json"

# Require config file as argument
if [ -z "$1" ]; then
    echo "Error: No config file provided. Usage: $0 path_to_config.json" >&2
    exit 1
fi

USER_CONFIG="$1"
CONFIG_FILE="$USER_CONFIG"
# If user config does not exist, error
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Provided config $CONFIG_FILE not found." >&2
    exit 1
fi

# Always load defaults first, then override with user config if present
TMP_DEFAULTS=$(mktemp)
TMP_USER=$(mktemp)
jq '.' "$DEFAULT_CONFIG" > "$TMP_DEFAULTS"
jq '.' "$CONFIG_FILE" > "$TMP_USER"



# Helper to get value: prefer user config, fallback to default
get_config_value() {
    local key="$1"
    local val
    val=$(jq -r --arg key "$key" '.[$key] // empty' "$TMP_USER")
    if [ -z "$val" ] || [ "$val" = "null" ]; then
        val=$(jq -r --arg key "$key" '.[$key] // empty' "$TMP_DEFAULTS")
    fi
    echo "$val"
}

# Get debug_on flag from config (default: false)
DEBUG_ON="$(get_config_value DEBUG_ON)"
if [ -z "$DEBUG_ON" ] || [ "$DEBUG_ON" = "null" ]; then
    DEBUG_ON="false"
fi
debug() {
    if [ "$DEBUG_ON" = "true" ]; then
        echo "[DEBUG] $@"
    fi
}





PACKAGE_NAME="$(get_config_value PACKAGE_NAME)"
debug "PACKAGE_NAME: $PACKAGE_NAME"
PYTHON_SCRIPT="$(get_config_value PYTHON_SCRIPT)"
debug "PYTHON_SCRIPT: $PYTHON_SCRIPT"
PYTHON_MODULES="$(get_config_value PYTHON_MODULES)" # directories, space separated list
debug "PYTHON_MODULES: $PYTHON_MODULES"

REQUIREMENTS_FILE="$(get_config_value REQUIREMENTS_FILE)"
debug "REQUIREMENTS_FILE: $REQUIREMENTS_FILE"
if [ -z "$REQUIREMENTS_FILE" ] || [ "$REQUIREMENTS_FILE" = "null" ]; then
    REQUIREMENTS_FILE="requirements.txt"
    debug "REQUIREMENTS_FILE not set, using default: $REQUIREMENTS_FILE"
fi



# Check required parameters
if [ -z "$PACKAGE_NAME" ] || [ "$PACKAGE_NAME" = "null" ]; then
    echo "Error: PACKAGE_NAME is a required parameter in the config file." >&2
    exit 1
fi
if [ -z "$PYTHON_SCRIPT" ] || [ "$PYTHON_SCRIPT" = "null" ]; then
    echo "Error: PYTHON_SCRIPT is a required parameter in the config file." >&2
    exit 1
fi
if [ -z "$PYTHON_MODULES" ] || [ "$PYTHON_MODULES" = "null" ]; then
    echo "Error: PYTHON_MODULES is a required parameter in the config file." >&2
    exit 1
fi
debug "Required parameters validated."


VERSION="$(get_config_value VERSION)"
debug "VERSION: $VERSION"
ARCHITECTURE="$(get_config_value ARCHITECTURE)"
debug "ARCHITECTURE: $ARCHITECTURE"
MAINTAINER="$(get_config_value MAINTAINER)"
debug "MAINTAINER: $MAINTAINER"
DESCRIPTION="$(get_config_value DESCRIPTION)"
debug "DESCRIPTION: $DESCRIPTION"
SERVICE="$(get_config_value SERVICE)"
if [ -z "$SERVICE" ] || [ "$SERVICE" = "null" ]; then
    SERVICE="$PACKAGE_NAME"
fi
debug "SERVICE: $SERVICE"
BUILDFOLDER="$(get_config_value BUILDFOLDER)"
debug "BUILDFOLDER: $BUILDFOLDER"
VENV_REQ_DIR="$(get_config_value VENV_REQ_DIR)"
debug "VENV_REQ_DIR: $VENV_REQ_DIR"

VENV_TARGET_DIR="$(get_config_value VENV_TARGET_DIR)"
if [ -z "$VENV_TARGET_DIR" ] || [ "$VENV_TARGET_DIR" = "null" ]; then
    VENV_TARGET_DIR="/usr/local/.venv.${PACKAGE_NAME}"
fi
debug "VENV_TARGET_DIR: $VENV_TARGET_DIR"


# Clean up temp files on exit
trap 'rm -f "$TMP_DEFAULTS" "$TMP_USER"' EXIT

# Remove existing build folder if it exists
if [ -d "${BUILDFOLDER}" ]; then
    debug "Removing existing build folder: ${BUILDFOLDER}"
    rm -rf ${BUILDFOLDER}
fi


# Create package directory structure
debug "Creating package directory structure."
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/systemd/system
mkdir -p ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}${VENV_TARGET_DIR}


# Create control file
debug "Creating control file."
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/control << EOF
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Architecture: ${ARCHITECTURE}
Maintainer: ${MAINTAINER}
Description: ${DESCRIPTION}
EOF


# Create preinst file
debug "Creating preinst file."
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/preinst << EOF
python3 -m venv --clear --system-site-packages ${VENV_TARGET_DIR}
EOF


# Create postinst file
debug "Creating postinst file."
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/postinst << EOF
if [ -d "${VENV_TARGET_DIR}/${VENV_REQ_DIR}" ]; then
    source ${VENV_TARGET_DIR}/bin/activate 
    sudo chown -R \$USER:\$USER ${VENV_TARGET_DIR}/${VENV_REQ_DIR}
    chmod -R u+rwX ${VENV_TARGET_DIR}/${VENV_REQ_DIR}
    pip3 install --no-index --find-links ${VENV_TARGET_DIR}/${VENV_REQ_DIR} -r ${VENV_TARGET_DIR}/${VENV_REQ_DIR}/requirements.txt > /dev/null
    deactivate
    # rm -rf ${VENV_TARGET_DIR}/${VENV_REQ_DIR}
fi
systemctl daemon-reload
systemctl enable ${SERVICE}
systemctl start ${SERVICE}
EOF


# Create prerm file
debug "Creating prerm file."
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/prerm << EOF
rm -rf ${VENV_TARGET_DIR}
systemctl stop ${SERVICE}
systemctl disable ${SERVICE}
EOF


# Create postrm file
debug "Creating postrm file."
cat > ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/postrm << EOF
EOF




# Build Python wheels and place them in VENV_REQ_DIR (optional)
if [ -n "$REQUIREMENTS_FILE" ] && [ -f "$REQUIREMENTS_FILE" ]; then
    debug "Building Python wheels from $REQUIREMENTS_FILE."
    mkdir -p "${VENV_REQ_DIR}"
    mkdir -p wheels_tmp
    pip wheel -r "$REQUIREMENTS_FILE" -w wheels_tmp
    for whl in wheels_tmp/*.whl; do
        debug "Processing wheel: $whl"
        auditwheel repair "$whl" -w "${VENV_REQ_DIR}" 2>/dev/null || cp "$whl" "${VENV_REQ_DIR}/"
    done
    rm -rf wheels_tmp
    if [ -n "$USER_ID" ] && [ -n "$GROUP_ID" ]; then
        debug "Setting ownership for $VENV_REQ_DIR to $USER_ID:$GROUP_ID"
        chown -R $USER_ID:$GROUP_ID "${VENV_REQ_DIR}" 2>/dev/null || true
    fi
    chmod -R a+rwX "${VENV_REQ_DIR}"
    # Copy requirements file into VENV_REQ_DIR for pip install
    cp "$REQUIREMENTS_FILE" "${VENV_REQ_DIR}/requirements.txt"
fi


# Copy the venv requirements dir
if [ -d "${VENV_REQ_DIR}" ]; then
    debug "Copying $VENV_REQ_DIR to build folder."
    cp -a ${VENV_REQ_DIR} ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}${VENV_TARGET_DIR}/
fi


# Copy python scripts
debug "Copying main script: $PYTHON_SCRIPT"
cp -a ${PYTHON_SCRIPT} ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}${VENV_TARGET_DIR}/
for MOD in ${PYTHON_MODULES}; do
    if [ -d "${MOD}" ]; then
        debug "Copying module directory: $MOD"
        cp -ar ${MOD} ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}${VENV_TARGET_DIR}/
    else
        debug "Module/directory $MOD not found, skipping."
    fi
done


# Get service template path from config, fallback to default
SERVICE_TEMPLATE="$(get_config_value SERVICE_TEMPLATE)"
if [ -z "$SERVICE_TEMPLATE" ] || [ "$SERVICE_TEMPLATE" = "null" ]; then
    SERVICE_TEMPLATE="/usr/local/bin/template.service.in"
fi
debug "Using service template: $SERVICE_TEMPLATE"
# Copy the service file (template) and replace start command
cp "$SERVICE_TEMPLATE" ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/systemd/system/${SERVICE}.service
sed -i "s|@EXEC_START@|/bin/bash -c 'source ${VENV_TARGET_DIR}/bin/activate \&\& CONFIG_PATH=\"/etc/motorcortex/config/services/${PACKAGE_NAME}.json\" python3 ${VENV_TARGET_DIR}/${PYTHON_SCRIPT}; deactivate'|g" ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/etc/systemd/system/${SERVICE}.service


# Set executable permissions
debug "Setting executable permissions for DEBIAN scripts."
chmod -f +x ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}/DEBIAN/{preinst,postinst,prerm,postrm}

echo "Debian package created: ${PACKAGE_NAME}_${VERSION}.deb"

# Build the package
debug "Building Debian package."
dpkg-deb -Zxz --build ${BUILDFOLDER}/${PACKAGE_NAME}_${VERSION}

echo "Debian package created: ${PACKAGE_NAME}_${VERSION}.deb"
# Ensure user has full rights over build folder and its contents
debug "Setting ownership and permissions for build folder."
if [ -n "$USER_ID" ] && [ -n "$GROUP_ID" ]; then
    chown -R $USER_ID:$GROUP_ID "${BUILDFOLDER}"
else
    # fallback: chown to current user if running interactively
    if [ -n "$SUDO_UID" ] && [ -n "$SUDO_GID" ]; then
        chown -R $SUDO_UID:$SUDO_GID "${BUILDFOLDER}"
    else
        chown -R $(id -u):$(id -g) "${BUILDFOLDER}"
    fi
fi
chmod -R a+rwX "${BUILDFOLDER}"
