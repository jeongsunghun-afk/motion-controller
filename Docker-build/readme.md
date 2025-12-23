


### Build a Debian package using the Docker container

First, build the image (in the `Docker-build/` directory):
```bash
docker build -t mcx-2025-03-37-deb-builder .
```

Then, from your project root, run:
```bash
docker run --rm -v "$PWD:/workspace" -w /workspace mcx-2025-03-37-deb-builder service_config.json
```

- Replace `service_config.json` with your own config file if needed.
- The resulting `.deb` file will be in your local `build/` directory.



The container includes `makeDeb.sh`, `default_service_config.json`, and `template.service.in` by default. You only need to provide your own config file as an argument.

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


---

## service_config.json Options

The `service_config.json` file is a JSON configuration file that controls how the Debian package is built. You can override any option from the default by specifying it in your config. Any missing option will fall back to the default (see `default_service_config.json`).

### Required options

- `PACKAGE_NAME` (string): Name of the package (used for .deb name, service, etc).
- `PYTHON_SCRIPT` (string): Main Python script to run as the service.
- `PYTHON_MODULES` (string): Space-separated list of directories to include (e.g. "src").



### Optional options

- `VERSION` (string): Package version. Default: "1.0"
- `ARCHITECTURE` (string): Target architecture. Default: "all"
- `MAINTAINER` (string): Maintainer info. Default: "Vectioneer B.V. <info@vectioneer.com>"
- `DESCRIPTION` (string): Description of the package. Default: "A client application for getting and setting data in a Motorcortex Control Application"
- `SERVICE` (string): Systemd service name. Default: same as `PACKAGE_NAME`.
- `BUILDFOLDER` (string): Build output folder. Default: "build"
- `VENV_REQ_DIR` (string): Directory for Python wheels/requirements. Default: "venv-req"
- `VENV_TARGET_DIR` (string): Target venv install dir. Default: `/usr/local/.venv.${PACKAGE_NAME}`
- `REQUIREMENTS_FILE` (string): Path to requirements.txt for building wheels. Optional. If not set or file missing, wheels are not built.
- `SERVICE_TEMPLATE` (string): Path to a custom systemd service template file. Optional. If not set, the default `template.service.in` included in the container is used.
- `DEBUG_ON` (bool): If true, enables verbose debug output in the build script. Default: false.

### Example

```json
{
	"PACKAGE_NAME": "my-app",
	"PYTHON_SCRIPT": "main.py",
	"PYTHON_MODULES": "src utils",
	"VERSION": "2.0",
	"DESCRIPTION": "My custom app",
	"REQUIREMENTS_FILE": "requirements.txt"
}
```

Any option not provided will be filled from `default_service_config.json` inside the container.

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