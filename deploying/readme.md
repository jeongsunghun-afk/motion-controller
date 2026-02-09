### Build a Debian package using the Docker container

First, build the image (in the `deploying/` directory):

```bash
docker build -t mcx-2025-03-37-deb-builder .
```

Then, from your project root, run:

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace mcx-2025-03-37-deb-builder package_config.json
```

The container includes `makeDeb.py`, `default_package_config.json`, and `template.service.in` by default. You only need to provide your config file as an argument.

If you want to use a custom systemd service template, add the `SERVICE_TEMPLATE` option to your config file, e.g.:

```json
{
  "PACKAGE_NAME": "my-app",
  "PYTHON_SCRIPT": "main.py",
  "PYTHON_MODULES": "src utils",
  "SERVICE_TEMPLATE": "/workspace/my_custom_template.service.in"
}
```

Your custom template file must be accessible inside the container (e.g. mounted via the Docker volume).

## package_config.json Options

The `package_config.json` file is a JSON configuration file that controls how the Debian package is built. You can override any option from the default by specifying it in your config. Any missing option will fall back to the default (see `default_package_config.json`).

Note: `makeDeb.py` reads the JSON keys shown below (uppercase keys are expected in your JSON). Internally they are mapped to lowercase fields (e.g. `BUILDFOLDER` -> `build_folder`) for use in the script.

### Required options

- `PACKAGE_NAME`: The name of the Debian package (example: "mcx-client-app"). Allowed characters: lowercase letters (a-z), digits (0-9) and hyphens (-).
- `PYTHON_SCRIPT`: The main Python script file to execute (example: "mcx-client-app.py"). This file is copied into the packaged venv directory.
- `PYTHON_MODULES`: Space-separated list of Python module directories to include in the package (example: "src utils").

### Optional options (full list)

- `DEPLOY_MODE`: Deployment mode, either `container` (default) or `venv` (not recommended). In `container` mode, the package is designed to run inside a Docker container. In `venv` mode, the package creates a virtual environment on the target system (Backwards compatible with older MCX images).
- `VERSION`: Package version (default from `default_package_config.json` or `1.0.0`).
- `ARCHITECTURE`: Debian architecture (default `all`).
- `MAINTAINER`: Maintainer field for the control file (default `Unknown`).
- `DESCRIPTION`: Package description (default: `Client application for {PACKAGE_NAME}`).
- `SERVICE`: Systemd service name (default: same as `PACKAGE_NAME`).
- `BUILDFOLDER`: Build folder path (default: `build`). The script will create `BUILDFOLDER/{PACKAGE_NAME}_{VERSION}`.
- `VENV_REQ_DIR`: Directory name used to store built wheels inside the build area (default: `wheels`).
- `VENV_TARGET_DIR`: Target path for the virtual environment on the target system (default: `/usr/local/.venv.{PACKAGE_NAME}`). This path is used in the generated service file and pre/postinstall scripts.
- `REQUIREMENTS_FILE`: Path to `requirements.txt` used to build wheels (optional). If present, wheels will be built and packaged into `VENV_REQ_DIR`.
- `SERVICE_TEMPLATE`: Path to a custom systemd service template file to use when generating the service unit (default: `template.service.in` from the `deploying/` folder or the value in `default_package_config.json`).
- `DEBUG_ON`: Enable debug/verbose output. Accepts `true`/`false`/`1`/`0` etc. When enabled the builder prints command output and extra debug information.

### Environment & runtime notes

- `makeDeb.py` accepts an optional `python_path` CLI argument which, when provided, forces the Python executable used to build wheels and to create the venv (example: `/usr/bin/python3.10`). If omitted the script tries `VIRTUAL_ENV`, `CONDA_PREFIX` or falls back to `python3`.
- When building inside Docker, set `HOST_UID` and `HOST_GID` environment variables on `docker run` so resulting build artifacts are chowned to the host user (the script tries `HOST_UID`/`HOST_GID`, then `SUDO_UID`/`SUDO_GID`, then the current uid/gid).

### Example

```json
{
  "PACKAGE_NAME": "my-app",
  "PYTHON_SCRIPT": "main.py",
  "PYTHON_MODULES": "src utils",
  "VERSION": "2.0",
  "ARCHITECTURE": "all",
  "MAINTAINER": "Your Name <you@example.com>",
  "DESCRIPTION": "My custom app",
  "SERVICE": "my-app",
  "BUILDFOLDER": "build",
  "VENV_REQ_DIR": "wheels",
  "VENV_TARGET_DIR": "/usr/local/.venv.my-app",
  "REQUIREMENTS_FILE": "requirements.txt",
  "SERVICE_TEMPLATE": "deploying/template.service.in",
  "DEBUG_ON": false
}
```

Any option not provided will be filled from `default_package_config.json` inside the container.

### Cleanup

Remove docker build:

```bash
docker rmi mcx-2025-03-37-deb-builder
```

Remove all Docker images:

```bash
docker rmi $(docker images -a -q)
```

Destroy them all forcefully:

```bash
docker container prune -f && docker rmi $(docker images -a -q --filter 'dangling=true') --force
```

## Using makeDeb.py Without Docker

You can also run `makeDeb.py` directly on your host system (outside Docker):

```bash
python3 deploying/makeDeb.py package_config.json
```

**Important:** When running locally, set the `SERVICE_TEMPLATE` option in your config to `deploying/template.service.in`:

```json
{
  "SERVICE_TEMPLATE": "deploying/template.service.in"
}
```

- Building Python wheels outside the Docker image may result in wheels that are not fully portable or compatible with the Motorcortex images.
