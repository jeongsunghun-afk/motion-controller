


### Build a Debian package using the Docker container

First, build the image (in the `Docker-build/` directory):
```bash
docker build -t mcx-2025-03-37-deb-builder .
```

Then, from your project root, run:
```bash
docker run --rm -v "$PWD:/workspace" -w /workspace mcx-2025-03-37-deb-builder service_config.json
```




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



## service_config.json Options

The `service_config.json` file is a JSON configuration file that controls how the Debian package is built. You can override any option from the default by specifying it in your config. Any missing option will fall back to the default (see `default_service_config.json`).

### Required options




### Optional options


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



## Using makeDeb.sh Without Docker

You can also run `makeDeb.sh` directly on your host system (outside Docker):

```bash
bash Docker-build/makeDeb.sh service_config.json
```

**Important:** When running locally, set the `SERVICE_TEMPLATE` option in your config to `Docker-build/template.service.in`:

```json
{
	"SERVICE_TEMPLATE": "Docker-build/template.service.in"
}
```

- Building Python wheels outside the Docker image may result in wheels that are not fully portable or compatible with the Motorcortex images.