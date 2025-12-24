# Motorcortex Client Application Template

**For complete documentation, see:** [Motorcortex Python Client Application Tools Documentation](https://docs.motorcortex.io/docs/developing-client-applications/python/usage/tools/)

## Overview

This template provides a ready-to-use structure for creating Python client applications that interact with Motorcortex servers. It includes everything needed to develop, test, and deploy your application as a Debian package compatible with MCX-RTOS.

## Quick Start

1. **Clone or download this template** (When using the Motorcortex VsCode extension, run the command "Motorcortex Utils: Create Python MCX Client App")
2. **Configure your application** by editing `config.json` and `service_config.json`
3. **Develop your application** by modifying `mcx-client-app.py` or creating new scripts
4. **Test locally** using the provided examples
5. **Build a Debian package** for deployment

## Project Structure

```
mcx-client-app-template/
├── mcx-client-app.py          # Main application template
├── config.json                # Runtime configuration
├── service_config.json        # Build configuration
├── examples/                  # Example applications
│   ├── robot_app.py          # Robot motion example
│   ├── start_button.py       # Start/stop button example
│   └── custom_button.py      # Custom GUI button example
├── src/mcx_client_app/       # Client application library
├── deploying/                 # Deployment tools
│   ├── makeDeb.sh            # Debian package builder
│   ├── Dockerfile            # Docker build environment
│   ├── template.service.in   # Systemd service template
│   └── readme.md             # Deployment documentation
└── venv-req/                  # Pre-built Python wheels
```

## Configuration Files

### `config.json` - Runtime Configuration

This file contains the connection settings and parameters for your application:

```json
{
    "target_url": "wss://localhost",
    "cert": "mcx.cert.pem",
    "login": "",
    "password": ""
}
```


### `service_config.json` - Build Configuration

This file controls how your Debian package is built:

```json
{
    "PACKAGE_NAME": "mcx-client-app-test",
    "PYTHON_SCRIPT": "mcx-client-app.py",
    "PYTHON_MODULES": "src",
    "VERSION": "1.0",
    "DESCRIPTION": "My custom Motorcortex client application"
}
```

See `deploying/readme.md` for a complete list of configuration options.

## Using the Template

### 1. Basic Application Structure

The template uses the `McxClientApp` base class which handles:
- Connection management
- State machine control (engage/disengage)
- Start/stop signal monitoring
- Automatic reconnection

Create your application by inheriting from `McxClientApp`:

```python
from src.mcx_client_app import McxClientApp, McxClientAppOptions

class MyApp(McxClientApp):
    def startOp(self):
        """Called after connection, before engaging"""
        # Initialize parameters, subscribe to data, etc.
        pass
    
    def action(self):
        """Main application loop"""
        # Your application logic here
        self.wait(1)  # Wait with stop signal support
    
    def onExit(self):
        """Called before disconnecting"""
        # Cleanup operations
        pass

if __name__ == "__main__":
    options = McxClientAppOptions(
        login="",
        password="",
        target_url="wss://localhost:5568:5567"
    )
    app = MyApp(options)
    app.run()
```

### 2. Explore the Examples

Check the `examples/` folder for working implementations:

- **`robot_app.py`** - Control a robot arm with motion programs
- **`start_button.py`** - Use a GUI button to start/stop your script
- **`custom_button.py`** - Create custom GUI controls and counters

### 3. Local Testing

Test your application locally before deploying:

```bash
python3 mcx-client-app.py
```

Or test with an example:

```bash
python3 examples/robot_app.py
```

### 4. Building a Debian Package

Use Docker to build a portable Debian package:

```bash
# Build the Docker image (first time only)
cd deploying
docker build -t mcx-2025-03-37-deb-builder .

# Build your Debian package
cd ..
docker run --rm -v "$PWD:/workspace" -w /workspace \
    mcx-2025-03-37-deb-builder service_config.json
```

The resulting `.deb` file will be in the `build/` folder.

### 5. Deployment

1. Upload your `.deb` package to the Motorcortex Portal
2. Install it on your target MCX-RTOS system
3. The application will automatically start as a systemd service
4. Control it from the Motorcortex GRID GUI or DESK tool

## Key Features

### Connection Management
- Automatic connection to Motorcortex server
- TLS/SSL support with certificate validation
- Automatic reconnection on connection loss

### State Machine Integration
- Built-in engage/disengage functionality
- Wait for specific states with timeout support
- Stop signal handling for graceful shutdown

### Start/Stop Control
- Optional start/stop parameter monitoring
- Automatic start/restart when button is pressed
- Clean shutdown when stopped

### Systemd Service
- Automatic startup with Motorcortex server
- Configurable restart behavior
- Proper dependency management

## Advanced Usage

### Custom Service Template

Create your own systemd service template by modifying `deploying/template.service.in` and referencing it in `service_config.json`:

```json
{
    "SERVICE_TEMPLATE": "/workspace/my_custom_template.service.in"
}
```

### Multiple Applications

Deploy multiple client applications by creating separate configuration files:

```bash
docker run --rm -v "$PWD:/workspace" -w /workspace \
    mcx-2025-03-37-deb-builder app1_config.json
docker run --rm -v "$PWD:/workspace" -w /workspace \
    mcx-2025-03-37-deb-builder app2_config.json
```

### Custom Dependencies

Add your own Python dependencies by editing `requirements.txt` and rebuilding the package.

## Common Use Cases

- **Automated Testing** - Run test sequences on your Motorcortex application
- **Motion Control** - Execute complex motion profiles for robots or AGVs
- **Data Logging** - Stream data to databases, InfluxDB, or time-series systems
- **Protocol Bridges** - Connect Motorcortex to MQTT, OPC-UA, ROS, or other middlewares
- **Custom Automation** - Implement application-specific behavior and workflows

## Troubleshooting

### Connection Issues
- Verify the `target_url` in `config.json`
- Check certificate path (use `/etc/ssl/certs/mcx.cert.pem` on MCX-RTOS)
- Ensure Motorcortex server is running and accessible

### Service Not Starting
- Check service status: `systemctl status your-service-name`
- View logs: `journalctl -u your-service-name -f`
- Verify Python virtual environment was created correctly

### Build Issues
- Ensure Docker is installed and running
- Check file permissions in the workspace
- Review build logs for specific errors

## Additional Resources

- [Motorcortex Documentation](https://docs.motorcortex.io/)
- [Python API Reference](https://docs.motorcortex.io/docs/developing-client-applications/python/)
- [Motorcortex Portal](https://motorcortex.io/)

## Support

For issues, questions, or contributions, please refer to the Motorcortex documentation or contact Vectioneer support.

