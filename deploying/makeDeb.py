#!/usr/bin/env python3
"""
makeDeb.py - Cross-platform Debian package builder for Motorcortex applications

This script builds Debian packages (.deb) with pure Python implementations,
"""

import json
import os
import sys
import shutil
import stat
import subprocess
import argparse
import tempfile
import re
from pathlib import Path
from pathlib import Path as _Path
import tarfile as _tarfile


class ArEntry:
    def __init__(self, name: str, data: bytes, mtime: int = 0, uid: int = 0, gid: int = 0, mode: int = 0o100644):
        self.name = name
        self.data = data
        self.mtime = mtime
        self.uid = uid
        self.gid = gid
        self.mode = mode

class ArArchive:
    ARMAG = b"!<arch>\n"
    
    def __init__(self, path, mode='r'):
        self.path = Path(path)
        self.mode = mode
        self.entries = []
        if 'r' in mode:
            self._read()

    def _read(self):
        with self.path.open('rb') as f:
            magic = f.read(8)
            if magic != self.ARMAG:
                raise ValueError("Not a valid ar archive")
            while True:
                header = f.read(60)
                if len(header) < 60:
                    break
                name = header[0:16].decode('utf-8').strip()
                mtime = int(header[16:28].decode('utf-8').strip())
                uid = int(header[28:34].decode('utf-8').strip())
                gid = int(header[34:40].decode('utf-8').strip())
                mode = int(header[40:48].decode('utf-8').strip(), 8)
                size = int(header[48:58].decode('utf-8').strip())
                end_chars = header[58:60]
                if end_chars != b'`\n':
                    raise ValueError("Invalid file header end characters")
                data = f.read(size)
                if size % 2 != 0:
                    f.read(1)  # padding
                self.entries.append(ArEntry(name, data, mtime, uid, gid, mode))

    def list(self):
        return [e.name for e in self.entries]

    def read(self, name):
        for e in self.entries:
            if e.name.strip() == name:
                return e.data
        raise KeyError(f"No such entry: {name}")

    def add(self, entry: ArEntry):
        if 'w' not in self.mode:
            raise ValueError("Archive not opened in write mode")
        self.entries.append(entry)

    def write(self, path=None):
        path = self.path if path is None else Path(path)
        with path.open('wb') as f:
            f.write(self.ARMAG)
            for e in self.entries:
                # prepare header
                name_field = e.name.encode('utf-8')[:16].ljust(16)
                mtime_field = str(e.mtime).encode('utf-8').ljust(12)
                uid_field = str(e.uid).encode('utf-8').ljust(6)
                gid_field = str(e.gid).encode('utf-8').ljust(6)
                mode_field = oct(e.mode)[2:].encode('utf-8').ljust(8)
                size_field = str(len(e.data)).encode('utf-8').ljust(10)
                header = name_field + mtime_field + uid_field + gid_field + mode_field + size_field + b'`\n'
                f.write(header)
                f.write(e.data)
                if len(e.data) % 2 != 0:
                    f.write(b'\n')  # padding


def debug_print(message, debug_enabled=False):
    """Print debug message if debugging is enabled."""
    if debug_enabled:
        print(f"[DEBUG] {message}")


def load_json_value(key, file_path):
    """Load a value from a JSON file, returning empty string on error."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get(key, '')
    except (FileNotFoundError, json.JSONDecodeError, IOError):
        return ''


def get_config_value(key, user_config, default_config):
    """Get config value from user config, falling back to default config."""
    value = load_json_value(key, user_config)
    if value:
        return value
    return load_json_value(key, default_config)


def run_command(cmd, cwd=None, debug_enabled=False, show_error=False):
    """Execute a shell command, returning (success, stdout, stderr) tuple."""
    debug_print(f"Running: {' '.join(cmd)}", debug_enabled)
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        if debug_enabled:
            if result.stdout.strip():
                print(f"STDOUT: {result.stdout}")
            if result.stderr.strip():
                print(f"STDERR: {result.stderr}")
        return True, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        debug_print(f"Command failed: {' '.join(cmd)} - {e}", debug_enabled)
        if show_error or debug_enabled:
            if e.stdout and e.stdout.strip():
                print(f"STDOUT: {e.stdout}", file=sys.stderr, flush=True)
            if e.stderr and e.stderr.strip():
                print(f"STDERR: {e.stderr}", file=sys.stderr, flush=True)
        return False, e.stdout or "", e.stderr or ""
    except FileNotFoundError as e:
        debug_print(f"Command not found: {' '.join(cmd)} - {e}", debug_enabled)
        if show_error or debug_enabled:
            print(f"Error: Command not found: {cmd[0]}", file=sys.stderr, flush=True)
        return False, "", str(e)


def determine_python_command(python_path_arg):
    """Determine which Python command to use."""
    if python_path_arg and os.path.exists(python_path_arg):
        return python_path_arg

    # Check for virtual environment
    if venv_path := os.environ.get('VIRTUAL_ENV'):
        return os.path.join(venv_path, 'bin', 'python')

    # Check for conda environment
    if os.environ.get('CONDA_DEFAULT_ENV') and (conda_prefix := os.environ.get('CONDA_PREFIX')):
        return os.path.join(conda_prefix, 'bin', 'python')

    return 'python3'


def load_package_config(config_file, default_config, python_cmd):
    """Load and validate package configuration."""
    debug_enabled = get_config_value('DEBUG_ON', config_file, default_config) in [True, 'true', '1', 1, "True", "TRUE"]

    # Required parameters
    package_name = get_config_value('PACKAGE_NAME', config_file, default_config)
    python_script = get_config_value('PYTHON_SCRIPT', config_file, default_config)
    python_modules = get_config_value('PYTHON_MODULES', config_file, default_config)

    if not all([package_name, python_script, python_modules]):
        missing = []
        if not package_name: missing.append('PACKAGE_NAME')
        if not python_script: missing.append('PYTHON_SCRIPT')
        if not python_modules: missing.append('PYTHON_MODULES')
        print(f"Error: Required config parameters missing: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # Optional parameters with defaults
    config = {
        'package_name': package_name,
        'python_script': python_script,
        'python_modules': python_modules,
        'version': get_config_value('VERSION', config_file, default_config) or '1.0.0',
        'architecture': get_config_value('ARCHITECTURE', config_file, default_config) or 'all',
        'maintainer': get_config_value('MAINTAINER', config_file, default_config) or 'Unknown',
        'description': get_config_value('DESCRIPTION', config_file, default_config) or f'Client application for {package_name}',
        'service': get_config_value('SERVICE', config_file, default_config) or package_name,
        'build_folder': get_config_value('BUILDFOLDER', config_file, default_config) or 'build',
        'venv_req_dir': get_config_value('VENV_REQ_DIR', config_file, default_config) or 'wheels',
        'requirements_file': get_config_value('REQUIREMENTS_FILE', config_file, default_config) or None,
        'deploy_mode': get_config_value('DEPLOY_MODE', config_file, default_config) or 'venv',
        'debug_enabled': debug_enabled
    }

    # Validate PACKAGE_NAME: only lowercase letters, digits and hyphens
    pkg_re = re.compile(r'^[a-z0-9-]+$')
    if not pkg_re.match(config['package_name']):
        print(f"Error: PACKAGE_NAME '{config['package_name']}' is invalid. Allowed characters: lowercase letters (a-z), digits (0-9), and hyphens (-). Example: my-service-1", file=sys.stderr)
        sys.exit(1)

    return config

def setup_build_directory(config):
    """Create the package build directory structure."""
    build_path = Path(config['build_folder'])
    if build_path.exists():
        debug_print(f"Removing existing build folder: {build_path}", config['debug_enabled'])
        try:
            if build_path.is_dir():
                    # Handle permission errors during removal
                    def _on_rm_error(func, path, exc_info):
                        try:
                            os.chmod(path, 0o777)
                            func(path)
                        except Exception:
                            pass

                    # Use the correct onerror keyword so errors are handled
                    shutil.rmtree(build_path, onerror=_on_rm_error)
            else:
                # If it's a file, unlink it
                build_path.unlink()
        except Exception as e:
            debug_print(f"Warning: Failed to remove existing build path: {e}", config['debug_enabled'])

    debug_print("Creating package directory structure", config['debug_enabled'])

    # Create main package directory
    package_dir = build_path / f"{config['package_name']}_{config['version']}"
    debian_dir = package_dir  / "DEBIAN"
    systemd_dir = package_dir / "data" / "etc" / "systemd" / "system"
    container_dir = package_dir / "data" / "opt" / config['package_name']

    # Create all directories
    for dir_path in [debian_dir, systemd_dir, container_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    return package_dir, debian_dir, systemd_dir, container_dir


def create_debian_metadata(config, debian_dir, systemd_dir, container_dir, script_dir, config_file_path):
    """Create Debian package metadata files."""
    debug_enabled = config['debug_enabled']

    # Control file
    debug_print("Creating control file", debug_enabled)
    
    # Set dependencies based on deployment mode
    if config['deploy_mode'] == 'container':
        depends = 'podman'
    else:
        depends = 'python3, python3-pip, python3-venv'
    
    control_content = f"""Package: {config['package_name']}
Version: {config['version']}
Architecture: {config['architecture']}
Maintainer: {config['maintainer']}
Description: {config['description']}
Depends: {depends}
"""
    try:
        # Ensure debian directory exists and is writable
        debian_dir.mkdir(parents=True, exist_ok=True)
        control_path = debian_dir / "control"
        control_path.write_text(control_content, encoding='utf-8', newline="\n")
        control_path.chmod(0o644)
    except Exception as e:
        debug_print(f"Failed to write control file {debian_dir / 'control'}: {e}", debug_enabled)
        raise

    # Pre-install script
    debug_print("Creating preinst script", debug_enabled)
    if config['deploy_mode'] == 'container':
        preinst_content = f"""#!/bin/bash
# Pre-install script for {config['package_name']} (container mode)
set -e

echo "Preparing for installation..."

# Stop service first to ensure clean state
if systemctl is-active --quiet {config['service']}; then
    echo "Stopping service {config['service']}..."
    systemctl stop {config['service']} || true
    # Wait for service to fully stop
    sleep 2
fi

# Force stop and remove any existing container
if /usr/bin/podman ps -a --format "{{{{.Names}}}}" | grep -q "^{config['package_name']}-container$"; then
    echo "Stopping existing container..."
    /usr/bin/podman stop -t 5 {config['package_name']}-container 2>/dev/null || true
    echo "Removing existing container..."
    /usr/bin/podman rm -f {config['package_name']}-container 2>/dev/null || true
    # Wait for cleanup
    sleep 1
fi

# Remove old images (try both with and without docker.io prefix)
for image_ref in "{config['package_name']}:{config['version']}" "docker.io/library/{config['package_name']}:{config['version']}" "localhost/{config['package_name']}:{config['version']}"; do
    if /usr/bin/podman images --format "{{{{.Repository}}}}:{{{{.Tag}}}}" | grep -q "^${{image_ref}}$"; then
        echo "Removing old container image: ${{image_ref}}..."
        /usr/bin/podman rmi -f "${{image_ref}}" 2>/dev/null || true
    fi
done

# Also remove any dangling images from this package
/usr/bin/podman images --filter "reference={config['package_name']}:{config['version']}" --format "{{{{.ID}}}}" | while read id; do
    if [ ! -z "$id" ]; then
        echo "Removing image ID: $id..."
        /usr/bin/podman rmi -f "$id" 2>/dev/null || true
    fi
done

echo "Pre-installation cleanup complete"
"""
    else:
        preinst_content = f"""#!/bin/bash
# Pre-install script for {config['package_name']} (venv mode)
# Stop service if running
systemctl stop {config['service']} 2>/dev/null || true
"""
    try:
        preinst_file = debian_dir / "preinst"
        preinst_file.write_text(preinst_content, encoding='utf-8', newline="\n")
        preinst_file.chmod(0o755)
    except Exception as e:
        debug_print(f"Failed to write preinst script: {e}", debug_enabled)
        raise

    # Post-install script
    debug_print("Creating postinst script", debug_enabled)
    if config['deploy_mode'] == 'container':
        postinst_content = f"""#!/bin/bash
# Post-install script for {config['package_name']} (container mode)
set -e

# Load container image
if [ -f "/opt/{config['package_name']}/{config['package_name']}-image.tar" ]; then
    echo "Loading container image..."
    if /usr/bin/podman load -i /opt/{config['package_name']}/{config['package_name']}-image.tar; then
        echo "Container image loaded successfully"
    else
        echo "ERROR: Failed to load container image" >&2
        exit 1
    fi
else
    echo "ERROR: Container image tar file not found at /opt/{config['package_name']}/{config['package_name']}-image.tar" >&2
    exit 1
fi

# Verify the image exists
echo "Verifying container image..."
/usr/bin/podman images
if ! /usr/bin/podman images | grep -q "{config['package_name']}.*{config['version']}"; then
    echo "ERROR: Container image {config['package_name']}:{config['version']} not found after loading" >&2
    echo "Available images:" >&2
    /usr/bin/podman images >&2
    exit 1
fi

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable {config['service']}

# Clean up the tar file after successful verification
rm -f /opt/{config['package_name']}/{config['package_name']}-image.tar

# Start the service
systemctl start {config['service']}
"""
    else:
        postinst_content = f"""#!/bin/bash
# Post-install script for {config['package_name']} (venv mode)
set -e

# Ensure directory exists and verify installation
if [ ! -d "/opt/{config['package_name']}" ]; then
    echo "ERROR: Installation directory /opt/{config['package_name']} does not exist" >&2
    echo "Package may not have unpacked correctly" >&2
    exit 1
fi

cd /opt/{config['package_name']}

# Verify main script exists
if [ ! -f "{config['python_script']}" ]; then
    echo "ERROR: Main script {config['python_script']} not found in /opt/{config['package_name']}" >&2
    echo "Package installation incomplete" >&2
    exit 1
fi

# Create virtual environment with system site packages
echo "Creating virtual environment with system packages..."
python3 -m venv --system-site-packages venv

# Install dependencies from wheels if available
if [ -d "wheels" ] && [ -f "wheels/requirements.txt" ]; then
    echo "Installing dependencies from wheels..."
    ./venv/bin/pip install --no-index --find-links wheels --root-user-action=ignore -r wheels/requirements.txt
fi

# Set proper permissions
chown -R admin:admin /opt/{config['package_name']}
chmod -R 755 /opt/{config['package_name']}

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable {config['service']}
systemctl start {config['service']}
"""
    try:
        postinst_file = debian_dir / "postinst"
        postinst_file.write_text(postinst_content, encoding='utf-8', newline="\n")
        postinst_file.chmod(0o755)
    except Exception as e:
        debug_print(f"Failed to write postinst script: {e}", debug_enabled)
        raise

    # Pre-remove script
    debug_print("Creating prerm script", debug_enabled)
    if config['deploy_mode'] == 'container':
        prerm_content = f"""#!/bin/bash
# Pre-remove script for {config['package_name']} (container mode)
systemctl stop {config['service']} || true
systemctl disable {config['service']} || true
# Stop and remove container
if /usr/bin/podman ps -a | grep -q {config['package_name']}-container; then
    /usr/bin/podman stop {config['package_name']}-container 2>/dev/null || true
    /usr/bin/podman rm {config['package_name']}-container 2>/dev/null || true
fi
"""
    else:
        prerm_content = f"""#!/bin/bash
# Pre-remove script for {config['package_name']} (venv mode)
systemctl stop {config['service']} || true
systemctl disable {config['service']} || true
"""
    try:
        prerm_file = debian_dir / "prerm"
        prerm_file.write_text(prerm_content, encoding='utf-8', newline="\n")
        prerm_file.chmod(0o755)
    except Exception as e:
        debug_print(f"Failed to write prerm script: {e}", debug_enabled)
        raise

    # Post-remove script
    debug_print("Creating postrm script", debug_enabled)
    if config['deploy_mode'] == 'container':
        postrm_content = f"""#!/bin/bash
# Post-remove script for {config['package_name']} (container mode)

# Only do full cleanup on purge or remove
if [ "$1" = "purge" ] || [ "$1" = "remove" ]; then
    echo "Cleaning up {config['package_name']}..."
    
    # Remove container images (try all possible references)
    for image_ref in "{config['package_name']}:{config['version']}" "docker.io/library/{config['package_name']}:{config['version']}" "localhost/{config['package_name']}:{config['version']}"; do
        if /usr/bin/podman images --format "{{{{.Repository}}}}:{{{{.Tag}}}}" | grep -q "^${{image_ref}}$" 2>/dev/null; then
            echo "Removing container image: ${{image_ref}}..."
            /usr/bin/podman rmi -f "${{image_ref}}" 2>/dev/null || true
        fi
    done
    
    # Clean up installation directory
    if [ -d "/opt/{config['package_name']}" ]; then
        echo "Removing installation directory..."
        rm -rf /opt/{config['package_name']}
    fi
    
    echo "Cleanup complete"
fi

# On upgrade, don't remove anything
exit 0
"""
    else:
        postrm_content = f"""#!/bin/bash
# Post-remove script for {config['package_name']} (venv mode)

# Only do full cleanup on purge or remove
if [ "$1" = "purge" ] || [ "$1" = "remove" ]; then
    echo "Cleaning up {config['package_name']}..."
    # Clean up installation directory
    if [ -d "/opt/{config['package_name']}" ]; then
        echo "Removing installation directory..."
        rm -rf /opt/{config['package_name']}
    fi
    echo "Cleanup complete"
fi

# On upgrade, don't remove anything
exit 0
"""
    try:
        postrm_path = debian_dir / "postrm"
        postrm_path.write_text(postrm_content, encoding='utf-8', newline="\n")
        postrm_path.chmod(0o755)
    except Exception as e:
        debug_print(f"Failed to write postrm script: {e}", debug_enabled)
        raise

    # Service file
    service_template = get_config_value('SERVICE_TEMPLATE', config_file_path, str(script_dir / 'default_package_config.json'))

    debug_print(f"Using service template: {service_template}", debug_enabled)

    service_file = systemd_dir / f"{config['service']}.service"

    # SERVICE_TEMPLATE - use default if not specified
    if not service_template:
        service_template = 'template.service.in'
        print(f"Using default SERVICE_TEMPLATE: {service_template}", flush=True)

    template_path = Path(service_template)
    if not template_path.exists():
        debug_print(f"Template not found at {template_path}, checking standard locations", debug_enabled)
        # Check in standard locations for Docker builds
        standard_locations = [
            Path('/usr/local/bin') / service_template,
            Path('/tmp') / service_template,
            script_dir / service_template,
            Path('deploying') / service_template
        ]
        
        for location in standard_locations:
            if location.exists():
                template_path = location
                debug_print(f"Found template at: {location}", debug_enabled)
                break
        else:
            print(f"Error: SERVICE_TEMPLATE '{service_template}' not found in workspace or standard locations", file=sys.stderr, flush=True)
            print(f"Searched: {[str(p) for p in standard_locations]}", file=sys.stderr, flush=True)
            sys.exit(1)

    if template_path.exists():
        debug_print(f"Using service template file: {template_path}")
        service_content = template_path.read_text()
        service_content = service_content.replace('@PACKAGE_NAME@', config['package_name'])
        service_content = service_content.replace('@VERSION@', config['version'])
        service_content = service_content.replace('@DESCRIPTION@', config['description'])
        service_content = service_content.replace('@PYTHON_SCRIPT@', config['python_script'])
        
        # Generate deployment-mode-specific content
        if config['deploy_mode'] == 'container':
            # Container deployment mode
            environment = "Environment=DEPLOYED=True"
            exec_start_pre = f"""ExecStartPre=-/bin/sh -c '/usr/bin/podman ps -a --format "{{{{.Names}}}}" | grep -q "^{config['package_name']}-container$" && /usr/bin/podman rm -f {config['package_name']}-container || true'
ExecStartPre=/bin/sh -c 'if ! /usr/bin/podman images | grep -q "{config['package_name']}.*{config['version']}"; then echo "ERROR: Container image {config['package_name']}:{config['version']} not found!" >&2; /usr/bin/podman images; exit 1; fi'"""
            exec_start = f"""podman run --rm --name {config['package_name']}-container \\
    --log-driver=none \\
    --network=host \\
    -v /etc/motorcortex:/etc/motorcortex:ro \\
    -v /etc/ssl/certs:/etc/ssl/certs:ro \\
    docker.io/library/{config['package_name']}:{config['version']} \\
    python3 /app/{config['python_script']}"""
            exec_stop = f"""ExecStop=/usr/bin/podman stop {config['package_name']}-container"""
        else:
            # Virtual environment deployment mode (default)
            environment = "Environment=DEPLOYED=True"
            exec_start_pre = ""
            exec_start = f"""/opt/{config['package_name']}/venv/bin/python3 /opt/{config['package_name']}/{config['python_script']}"""
            exec_stop = ""
        
        service_content = service_content.replace('@ENVIRONMENT@', environment)
        service_content = service_content.replace('@EXEC_START_PRE@', exec_start_pre)
        service_content = service_content.replace('@EXEC_START@', exec_start)
        service_content = service_content.replace('@EXEC_STOP@', exec_stop)
        
        service_file.write_text(service_content, encoding='utf-8', newline="\n")
    else:
        print(f"Error: Service template {template_path} not found", file=sys.stderr)
        sys.exit(1)


def build_python_wheels(config, python_cmd):
    """Build Python wheels from requirements file."""
    if config['requirements_file'] is None:
        debug_print("No REQUIREMENTS_FILE specified, skipping wheel building", config['debug_enabled'])
        return
    
    req_file = Path(config['requirements_file'])
    if not req_file.exists():
        print(f"Warning: Requirements file not found at {req_file.absolute()}", file=sys.stderr)
        print(f"Current working directory: {Path.cwd()}", file=sys.stderr)
        return

    print(f"Building Python wheels from {req_file}", flush=True)
    debug_print(f"Building Python wheels from {req_file}", config['debug_enabled'])
    
    # Show contents of requirements file
    try:
        with open(req_file, 'r') as f:
            req_contents = f.read().strip()
            req_lines = [line.strip() for line in req_contents.split('\n') if line.strip() and not line.strip().startswith('#')]
            if req_lines:
                print(f"Requirements file contains {len(req_lines)} package(s):", flush=True)
                for line in req_lines[:5]:  # Show first 5
                    print(f"  - {line}", flush=True)
                if len(req_lines) > 5:
                    print(f"  ... and {len(req_lines) - 5} more", flush=True)
            else:
                print("Warning: Requirements file is empty or contains only comments", flush=True)
                return
    except Exception as e:
        print(f"Warning: Could not read requirements file: {e}", file=sys.stderr)
        return

    wheels_dir = Path(config['venv_req_dir'])
    wheels_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Build wheels
        print(f"Running: {python_cmd} -m pip wheel -r {req_file}", flush=True)
        success, stdout, stderr = run_command(
            [python_cmd, '-m', 'pip', 'wheel', '-r', str(req_file), '-w', str(tmp_path)],
            cwd=Path.cwd(), debug_enabled=config['debug_enabled'], show_error=True
        )
        if not success:
            print("Warning: Failed to build wheels", file=sys.stderr, flush=True)
            return

        # Count wheels built
        wheel_files = list(tmp_path.glob('*.whl'))
        print(f"Built {len(wheel_files)} wheel(s)", flush=True)
        
        # Process each wheel
        for whl_file in wheel_files:
            debug_print(f"Processing wheel: {whl_file.name}", config['debug_enabled'])

            # Try auditwheel repair, fallback to copy
            success, _, _ = run_command(['auditwheel', 'repair', str(whl_file), '-w', str(wheels_dir)],
                                       cwd=Path.cwd(), debug_enabled=config['debug_enabled'])
            if not success:
                try:
                    shutil.copy2(str(whl_file), str(wheels_dir))
                except (OSError, IOError) as e:
                    debug_print(f"Warning: Failed to copy wheel {whl_file.name}: {e}", config['debug_enabled'])

    # Set permissions safely
    for file_path in wheels_dir.rglob('*'):
        try:
            if file_path.is_file():
                file_path.chmod(0o664)
            elif file_path.is_dir():
                file_path.chmod(0o775)
        except (OSError, PermissionError):
            pass  # Ignore permission errors

    # Copy requirements file
    try:
        shutil.copy2(str(req_file), str(wheels_dir / 'requirements.txt'))
    except (OSError, IOError) as e:
        debug_print(f"Warning: Failed to copy requirements file: {e}", config['debug_enabled'])
    
    # Set ownership to host user for wheels directory (important for Docker builds)
    try:
        _set_ownership_recursive(wheels_dir, config['debug_enabled'])
    except Exception as e:
        debug_print(f"Warning: Failed to set ownership on wheels directory: {e}", config['debug_enabled'])


def copy_app_files_for_venv(config, container_dir):
    """Copy application files for virtual environment deployment."""
    debug_enabled = config['debug_enabled']
    debug_print("Copying application files for venv deployment", debug_enabled)
    
    # Copy main Python script
    script_src = Path(config['python_script'])
    if script_src.exists():
        debug_print(f"Copying main script: {script_src}", debug_enabled)
        shutil.copy2(str(script_src), str(container_dir / script_src.name))
    else:
        print(f"Error: Python script {script_src} not found", file=sys.stderr)
        sys.exit(1)
    
    # Copy Python modules
    for module in config['python_modules'].split():
        module_path = Path(module)
        if module_path.is_dir():
            debug_print(f"Copying module: {module}", debug_enabled)
            shutil.copytree(str(module_path), str(container_dir / module_path.name), dirs_exist_ok=True)
        elif module_path.is_file():
            debug_print(f"Copying module file: {module}", debug_enabled)
            shutil.copy2(str(module_path), str(container_dir / module_path.name))
        else:
            print(f"Warning: Module/directory {module} not found, skipping", file=sys.stderr)
    
    # Copy wheels directory if it exists
    wheels_src = Path(config['venv_req_dir'])
    if wheels_src.exists() and wheels_src.is_dir():
        debug_print(f"Copying wheels from {wheels_src}", debug_enabled)
        shutil.copytree(str(wheels_src), str(container_dir / 'wheels'), dirs_exist_ok=True)
    
    debug_print("Application files copied successfully", debug_enabled)


def build_container_image(config, container_dir):
    """Build container image and export it as a tar file."""
    debug_enabled = config['debug_enabled']
    debug_print("Building container image", debug_enabled)
    
    # Detect available container runtime (prefer docker when socket is available)
    container_cmd = None
    
    # Check if docker socket is available (Docker-in-Docker or Docker socket mount)
    if os.path.exists('/var/run/docker.sock'):
        # Prefer docker when socket is available
        success, _, _ = run_command(['docker', '--version'], cwd=Path.cwd(), debug_enabled=False)
        if success:
            container_cmd = 'docker'
            debug_print(f"Using Docker via socket mount", debug_enabled)
    
    # Fall back to checking both docker and podman
    if not container_cmd:
        for cmd in ['docker', 'podman']:
            success, _, _ = run_command([cmd, '--version'], cwd=Path.cwd(), debug_enabled=False)
            if success:
                container_cmd = cmd
                debug_print(f"Using container runtime: {cmd}", debug_enabled)
                break
    
    if not container_cmd:
        print("Error: Neither docker nor podman found", file=sys.stderr)
        sys.exit(1)
    
    # Create temporary build directory
    with tempfile.TemporaryDirectory() as build_context:
        build_context_path = Path(build_context)
        
        # Copy Dockerfile
        dockerfile_src = Path('deploying/app.Dockerfile')
        if not dockerfile_src.exists():
            dockerfile_src = Path('app.Dockerfile')
        if not dockerfile_src.exists():
            print("Error: app.Dockerfile not found", file=sys.stderr)
            sys.exit(1)
        
        shutil.copy2(str(dockerfile_src), str(build_context_path / 'Dockerfile'))
        debug_print(f"Copied Dockerfile to build context", debug_enabled)
        
        # Copy wheels directory
        wheels_src = Path(config['venv_req_dir'])
        if wheels_src.exists():
            debug_print(f"Copying wheels from {wheels_src}", debug_enabled)
            shutil.copytree(str(wheels_src), str(build_context_path / 'wheels'), dirs_exist_ok=True)
        
        # Copy main Python script
        script_src = Path(config['python_script'])
        if script_src.exists():
            debug_print(f"Copying main script: {script_src}", debug_enabled)
            shutil.copy2(str(script_src), str(build_context_path / script_src.name))
        else:
            debug_print(f"Warning: Python script {script_src} not found", debug_enabled)
        
        # Copy Python modules
        for module in config['python_modules'].split():
            module_path = Path(module)
            if module_path.is_dir():
                debug_print(f"Copying module: {module}", debug_enabled)
                shutil.copytree(str(module_path), str(build_context_path / module_path.name), dirs_exist_ok=True)
            else:
                debug_print(f"Module/directory {module} not found, skipping", debug_enabled)
        
        # Build the image
        image_name = f"{config['package_name']}:{config['version']}"
        build_cmd = [container_cmd, 'build', '-t', image_name, '.']
        
        print(f"Building container image: {image_name}", flush=True)
        # Always show output for container build (critical step)
        success, _, _ = run_command(build_cmd, cwd=build_context_path, debug_enabled=True, show_error=True)
        if not success:
            print("Error: Failed to build container image", file=sys.stderr)
            print(f"Build context directory: {build_context_path}", file=sys.stderr)
            print(f"Check that app.Dockerfile and all required files are present", file=sys.stderr)
            sys.exit(1)
        
        # Export the image to a tar file
        tar_file = container_dir / f"{config['package_name']}-image.tar"
        export_cmd = [container_cmd, 'save', '-o', str(tar_file), image_name]
        
        debug_print(f"Exporting image to {tar_file}", debug_enabled)
        success, _, _ = run_command(export_cmd, cwd=Path.cwd(), debug_enabled=debug_enabled, show_error=True)
        if not success:
            print("Error: Failed to export container image", file=sys.stderr)
            sys.exit(1)
        
        debug_print(f"Container image exported successfully to {tar_file}", debug_enabled)
        
        # Clean up the built image from local storage to save space
        cleanup_cmd = [container_cmd, 'rmi', image_name]
        run_command(cleanup_cmd, cwd=Path.cwd(), debug_enabled=debug_enabled)


def create_debian_binary(package_dir:str, debug_enabled:bool=False) -> bool:
    """Create a text file indicating Debian binary format."""
    debug_print("Creating debian-binary file", debug_enabled)
    try:
        debian_binary_path = package_dir / "debian-binary"
        debian_binary_path.write_text("2.0\n", encoding='utf-8', newline="\n")
        debian_binary_path.chmod(0o644)
        return True
    except Exception as e:
        debug_print(f"Failed to create debian-binary file: {e}", debug_enabled)
        return False
    
def build_deb(package_dir: str, output_file: str, config: dict) -> bool:
    package_dir = Path(package_dir)
    DEBIAN = package_dir / "DEBIAN"
    data_folder = package_dir / "data"

    if not DEBIAN.exists() or not data_folder.exists():
        print("DEBIAN or data folder missing")
        return False

    # Step 1: debian-binary
    debian_binary = package_dir / "debian-binary"
    debian_binary.write_text("2.0\n", newline="\n")

    # Step 2: control.tar.gz
    with _tarfile.open(package_dir / "control.tar.gz", "w:gz", format=_tarfile.GNU_FORMAT) as tf:
        if DEBIAN.exists():
            for item in sorted(DEBIAN.rglob('*')):
                try:
                    rel = item.relative_to(DEBIAN)
                except Exception:
                    # Skip entries that are not under DEBIAN for safety
                    continue
                tf.add(item, arcname=str(rel), recursive=True)

    # Step 3: data.tar.gz
    with _tarfile.open(package_dir / "data.tar.gz", "w:gz", format=_tarfile.GNU_FORMAT) as tf:
        # Add files preserving paths relative to the data folder (e.g. etc/... , usr/...)
        # Use rglob to ensure we only include entries actually under data_folder and
        # compute their relative paths safely.
        if data_folder.exists():
            for path in sorted(data_folder.rglob('*')):
                try:
                    rel = path.relative_to(data_folder)
                except Exception:
                    continue
                tf.add(path, arcname=str(rel), recursive=False)

    # Step 4: combine using ar
    ar_archive = ArArchive(output_file, mode='w')
    for filename in ["debian-binary", "control.tar.gz", "data.tar.gz"]:
        file_path = package_dir / filename
        with file_path.open('rb') as f:
            data = f.read()
        ar_archive.add(ArEntry(filename, data))
    ar_archive.write(output_file)

    # # Optional cleanup
    # for f in ["debian-binary", "control.tar.gz", "data.tar.gz"]:
    #     (package_dir / f).unlink()
    
    print(f"Created Debian package: {output_file}")
    return True
        


def build_debian_package(package_dir, config):
    """Build the final Debian package using the best available tool."""
    debug_enabled = config['debug_enabled']
    debug_print("Building Debian package", debug_enabled)
    # Fallback to nfpm
    output_file_simple = Path(config['build_folder']) / f"{config['package_name']}_{config['version']}.deb"
    
    # Create debian-binary file
    create_debian_binary(package_dir, config['debug_enabled'])
    
    if build_deb(package_dir, output_file_simple, config):
        print(f"Debian package created: {output_file_simple.name}")
    else:
        print("Failed to build Debian package", file=sys.stderr)


def set_build_permissions(build_path, debug_enabled):
    """Set appropriate permissions on build artifacts."""
    debug_print("Setting permissions on build folder", debug_enabled)
    for file_path in build_path.rglob('*'):
        try:
            if file_path.is_file():
                file_path.chmod(0o664)
            elif file_path.is_dir():
                file_path.chmod(0o775)
        except (OSError, PermissionError):
            pass  # Ignore permission errors on restrictive filesystems


def _set_ownership_recursive(target_path, debug_enabled=False):
    """Set ownership recursively for a given path to host user.
    
    This tries, in order:
    - Use HOST_UID / HOST_GID environment variables (set by Docker run)
    - Use SUDO_UID / SUDO_GID if running under sudo
    - Fallback to current process uid/gid
    Skips ownership changes on Windows.
    """
    try:
        if os.name == 'nt':
            debug_print('Skipping ownership change on Windows', debug_enabled)
            return

        # Resolve absolute path
        target = Path(target_path).resolve()
        
        if not target.exists():
            return

        # Determine target uid/gid
        host_uid = os.environ.get('HOST_UID')
        host_gid = os.environ.get('HOST_GID')
        if host_uid and host_gid:
            uid = int(host_uid)
            gid = int(host_gid)
        else:
            sudo_uid = os.environ.get('SUDO_UID')
            sudo_gid = os.environ.get('SUDO_GID')
            if sudo_uid and sudo_gid:
                uid = int(sudo_uid)
                gid = int(sudo_gid)
            else:
                uid = os.getuid()
                gid = os.getgid()

        debug_print(f"Setting ownership to {uid}:{gid} for {target}", debug_enabled)

        # Walk and chown
        for root, dirs, files in os.walk(str(target)):
            for d in dirs:
                try:
                    os.chown(os.path.join(root, d), uid, gid)
                except Exception:
                    pass
            for f in files:
                try:
                    os.chown(os.path.join(root, f), uid, gid)
                except Exception:
                    pass

        try:
            os.chown(str(target), uid, gid)
        except Exception:
            pass

    except Exception as e:
        debug_print(f'Failed to set ownership for {target_path}: {e}', debug_enabled)


def finalize_permissions_and_ownership(build_folder, debug_enabled=False):
    """Ensure build folder permissions and set ownership to host user if possible.

    This tries, in order:
    - Use HOST_UID / HOST_GID environment variables (set by Docker run)
    - Use SUDO_UID / SUDO_GID if running under sudo
    - Fallback to current process uid/gid
    Skips ownership changes on Windows.
    """
    _set_ownership_recursive(build_folder, debug_enabled)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Build Debian package for Motorcortex application')
    parser.add_argument('config_file', help='Path to service config JSON file')
    parser.add_argument('python_path', nargs='?', default='', help='Python executable path (optional)')
    args = parser.parse_args()

    # Validate config file exists
    config_file = Path(args.config_file)
    if not config_file.exists():
        print(f"Error: Config file {config_file} not found", file=sys.stderr)
        sys.exit(1)

    # Setup paths
    script_dir = Path(__file__).parent
    default_config = script_dir / 'default_package_config.json'

    # Determine Python command
    python_cmd = determine_python_command(args.python_path)
    debug_print(f"Using Python: {python_cmd}")

    # Load configuration
    config = load_package_config(str(config_file), str(default_config), python_cmd)

    # Print config summary
    print("Configuration loaded:", flush=True)
    for key, value in config.items():
        if key != 'debug_enabled':
            print(f"  {key.upper()}: {value}", flush=True)

    # Setup build directory
    package_dir, debian_dir, systemd_dir, container_dir = setup_build_directory(config)

    # Create Debian metadata
    create_debian_metadata(config, debian_dir, systemd_dir, container_dir, script_dir, str(config_file))

    # Build Python wheels
    build_python_wheels(config, python_cmd)

    # Build container image or copy app files based on deployment mode
    if config['deploy_mode'] == 'container':
        print("Building container image for container deployment...", flush=True)
        build_container_image(config, container_dir)
    else:
        print("Copying application files for venv deployment...", flush=True)
        copy_app_files_for_venv(config, container_dir)

    # Build the final package
    build_debian_package(package_dir, config)

    # Set final permissions
    set_build_permissions(Path(config['build_folder']), config['debug_enabled'])

    # Ensure files are owned by the invoking user (use HOST_UID/HOST_GID from Docker,
    # or SUDO_UID fallback, or current uid/gid). This prevents root-owned build artifacts
    # when running inside containers or under sudo.
    try:
        finalize_permissions_and_ownership(config['build_folder'], config['debug_enabled'])
    except Exception:
        # Do not fail the build for ownership fix failures; just log in debug mode
        debug_print('finalize_permissions_and_ownership failed', config['debug_enabled'])


if __name__ == '__main__':
    main()