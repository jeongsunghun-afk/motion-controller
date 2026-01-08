#!/usr/bin/env python3
"""
makeDeb.py - Cross-platform Debian package builder for Motorcortex applications

This script builds Debian packages (.deb) with pure Python implementations,
"""

import json
import os
import sys
import shutil
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


def run_command(cmd, cwd=None, debug_enabled=False):
    """Execute a shell command, returning True on success."""
    debug_print(f"Running: {' '.join(cmd)}", debug_enabled)
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        if debug_enabled:
            if result.stdout.strip():
                print(f"STDOUT: {result.stdout}")
            if result.stderr.strip():
                print(f"STDERR: {result.stderr}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        debug_print(f"Command failed: {' '.join(cmd)} - {e}", debug_enabled)
        return False


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
        'venv_target_dir': get_config_value('VENV_TARGET_DIR', config_file, default_config) or f'/usr/local/.venv.{package_name}',
        'requirements_file': get_config_value('REQUIREMENTS_FILE', config_file, default_config) or None,
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
    venv_dir = package_dir / "data" / config['venv_target_dir'].lstrip('/')

    # Create all directories
    for dir_path in [debian_dir, systemd_dir, venv_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)

    return package_dir, debian_dir, systemd_dir, venv_dir


def create_debian_metadata(config, debian_dir, systemd_dir, venv_dir, script_dir, config_file_path):
    """Create Debian package metadata files."""
    debug_enabled = config['debug_enabled']

    # Control file
    debug_print("Creating control file", debug_enabled)
    control_content = f"""Package: {config['package_name']}
Version: {config['version']}
Architecture: {config['architecture']}
Maintainer: {config['maintainer']}
Description: {config['description']}
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
    preinst_content = f"{determine_python_command('')} -m venv --clear --system-site-packages {config['venv_target_dir']}\n"
    try:
        preinst_file = debian_dir / "preinst"
        preinst_file.write_text(preinst_content, encoding='utf-8', newline="\n")
        preinst_file.chmod(0o755)
    except Exception as e:
        debug_print(f"Failed to write preinst script: {e}", debug_enabled)
        raise

    # Post-install script
    debug_print("Creating postinst script", debug_enabled)
    postinst_content = f"""if [ -d "{config['venv_target_dir']}/{config['venv_req_dir']}" ]; then
    source {config['venv_target_dir']}/bin/activate
    sudo chown -R $USER:$USER {config['venv_target_dir']}/{config['venv_req_dir']}
    chmod -R u+rwX {config['venv_target_dir']}/{config['venv_req_dir']}
    pip3 install --no-index --find-links {config['venv_target_dir']}/{config['venv_req_dir']} -r {config['venv_target_dir']}/{config['venv_req_dir']}/requirements.txt > /dev/null
    deactivate
fi
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
    prerm_content = f"""rm -rf {config['venv_target_dir']}
systemctl stop {config['service']}
systemctl disable {config['service']}
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
    try:
        postrm_path = debian_dir / "postrm"
        postrm_path.write_text("", encoding='utf-8', newline="\n")
        postrm_path.chmod(0o755)
    except Exception as e:
        debug_print(f"Failed to write postrm script: {e}", debug_enabled)
        raise

    # Service file
    service_template = get_config_value('SERVICE_TEMPLATE', config_file_path, str(script_dir / 'default_service_config.json'))

    debug_print(f"Using service template: {service_template}", debug_enabled)

    service_file = systemd_dir / f"{config['service']}.service"

    # SERVICE_TEMPLATE - use default if not specified
    if not service_template:
        service_template = 'template.service.in'
        print(f"Using default SERVICE_TEMPLATE: {service_template}", flush=True)

    template_path = Path(service_template)
    if not template_path.exists():
        print(f"Template not found at {template_path}, checking /tmp/", flush=True)
        # Check in /tmp for Docker builds where template is copied
        tmp_path = Path('/tmp') / service_template
        if tmp_path.exists():
            template_path = tmp_path
            debug_print(f"Found specified template in /tmp: {tmp_path}")
        else:
            print(f"Error: Specified SERVICE_TEMPLATE '{service_template}' not found in workspace or /tmp", file=sys.stderr, flush=True)
            sys.exit(1)

    if template_path.exists():
        debug_print(f"Using service template file: {template_path}")
        service_content = template_path.read_text()
        service_content = service_content.replace('@EXEC_START@',
            f'/bin/bash -c \'source {config["venv_target_dir"]}/bin/activate && DEPLOYED=True python3 {config["venv_target_dir"]}/{config["python_script"]}; deactivate\'')
        service_content = service_content.replace('@DESCRIPTION@', config['description'])
        service_file.write_text(service_content, encoding='utf-8', newline="\n")
    else:
        print(f"Error: Service template {template_path} not found", file=sys.stderr)
        sys.exit(1)


def build_python_wheels(config, python_cmd):
    """Build Python wheels from requirements file."""
    if config['requirements_file'] is None:
        return
    
    req_file = Path(config['requirements_file'])
    if not req_file.exists():
        return

    debug_print(f"Building Python wheels from {req_file}", config['debug_enabled'])

    wheels_dir = Path(config['venv_req_dir'])
    wheels_dir.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Build wheels
        if not run_command([python_cmd, '-m', 'pip', 'wheel', '-r', str(req_file), '-w', str(tmp_path)],
                          cwd=Path.cwd(), debug_enabled=config['debug_enabled']):
            debug_print("Warning: Failed to build wheels", config['debug_enabled'])
            return

        # Process each wheel
        for whl_file in tmp_path.glob('*.whl'):
            debug_print(f"Processing wheel: {whl_file.name}", config['debug_enabled'])

            # Try auditwheel repair, fallback to copy
            if not run_command(['auditwheel', 'repair', str(whl_file), '-w', str(wheels_dir)],
                              cwd=Path.cwd(), debug_enabled=config['debug_enabled']):
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


def copy_application_files(config, venv_dir):
    """Copy Python application files to the package."""
    debug_enabled = config['debug_enabled']

    # Copy wheels directory
    wheels_src = Path(config['venv_req_dir'])
    if wheels_src.exists():
        debug_print(f"Copying wheels from {wheels_src}", debug_enabled)
        shutil.copytree(str(wheels_src), str(venv_dir / config['venv_req_dir']), dirs_exist_ok=True)

    # Copy main Python script
    script_src = Path(config['python_script'])
    if script_src.exists():
        debug_print(f"Copying main script: {script_src}", debug_enabled)
        shutil.copy2(str(script_src), str(venv_dir))
    else:
        debug_print(f"Warning: Python script {script_src} not found", debug_enabled)

    # Copy Python modules
    for module in config['python_modules'].split():
        module_path = Path(module)
        if module_path.is_dir():
            debug_print(f"Copying module: {module}", debug_enabled)
            shutil.copytree(str(module_path), str(venv_dir / module_path.name), dirs_exist_ok=True)
        else:
            debug_print(f"Module/directory {module} not found, skipping", debug_enabled)
            
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
                tf.add(path, arcname=str(rel))

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


def finalize_permissions_and_ownership(build_folder, debug_enabled=False):
    """Ensure build folder permissions and set ownership to host user if possible.

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
        build_path = Path(build_folder).resolve()

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

        debug_print(f"Setting ownership to {uid}:{gid} for {build_path}", debug_enabled)

        # Walk and chown
        for root, dirs, files in os.walk(str(build_path)):
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
            os.chown(str(build_path), uid, gid)
        except Exception:
            pass

    except Exception as e:
        debug_print(f'Failed to finalize ownership/permissions: {e}', debug_enabled)


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
    default_config = script_dir / 'default_service_config.json'

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
    package_dir, debian_dir, systemd_dir, venv_dir = setup_build_directory(config)

    # Create Debian metadata
    create_debian_metadata(config, debian_dir, systemd_dir, venv_dir, script_dir, str(config_file))

    # Build Python wheels
    build_python_wheels(config, python_cmd)

    # Copy application files
    copy_application_files(config, venv_dir)

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