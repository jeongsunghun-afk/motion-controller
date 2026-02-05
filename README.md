# Motorcortex Client Application Template

**For complete documentation, see:** [Motorcortex Python Client Application Tools Documentation](https://docs.motorcortex.io/docs/developing-client-applications/python/usage/tools/)

## Overview

This template provides a ready-to-use structure for creating Python applications that interact with Motorcortex servers. MCX-Client-Apps connect to a Motorcortex control system via WebSocket to monitor parameters, control robots, automate workflows, and integrate with external systems. The template includes everything needed to develop, test, and deploy your application as a Debian package compatible with MCX-RTOS.

## Quick Start

1. **Clone or download this template** (When using the Motorcortex VsCode extension, run the command "Motorcortex Utils: Create Python MCX Client App")
2. **Configure your service** by editing `services_config.json`
3. **Develop your application** by modifying `mcx-client-app.py` or creating new scripts
4. **Test locally** using the provided examples
5. **Build a Debian package** for deployment

## How Client Apps Work

MCX-Client-Apps interact with the **Motorcortex parameter tree** - a hierarchical structure containing system parameters. Your app can:

- **Read parameters** with `self.req.getParameter()`
- **Write parameters** with `self.req.setParameter()`  
- **Subscribe for real-time updates** with `self.sub.subscribe()`

All custom service parameters are automatically placed under `root/Services/{ServiceName}/serviceParameters/` when defined in your service configuration.

## Project Structure

```
mcx-client-app-template/
├── mcx-client-app.py          # Main application template
├── services_config.json       # Service configuration (connection, parameters)
├── package_config.json        # Build configuration
├── examples/                  # Example applications
│   ├── robot_app.py          # Robot motion example
│   ├── start_button.py       # Start/stop button example
│   ├── custom_button.py      # Custom GUI button example
│   ├── error_app.py          # Error handler example
│   └── datalogger.py         # Data logging example
├── src/mcx_client_app/       # Client application library
│   ├── McxClientApp.py       # Base classes
│   ├── McxClientAppConfiguration.py  # Configuration class
│   ├── McxWatchdog.py        # Watchdog manager
│   ├── McxErrorHandler.py    # Error handling
│   └── ChangeDetector.py     # Change detection utility
├── deploying/                 # Deployment tools
│   ├── makeDeb.py            # Debian package builder
│   ├── Dockerfile            # Docker build environment
│   ├── template.service.in   # Systemd service template
│   └── readme.md             # Deployment documentation
└── venv-req/                  # Pre-built Python wheels
```

## Configuration Files

### `services_config.json` - Service Configuration

This file defines your service(s) with connection settings, parameters, and behavior:

```json
{
  "Services": [
    {
      "Name": "mcx-client-app",
      "Enabled": true,
      "Config": {
        "login": "admin",
        "password": "your_password",
        "target_url": "wss://192.168.1.100",
        "autoStart": true
      },
      "Parameters": {
        "Version": "1.0",
        "Children": [
          {
            "Name": "userParameters",
            "Children": [
              {
                "Name": "StartButton",
                "Type": "bool, input",
                "Value": 0
              },
              {
                "Name": "Counter",
                "Type": "int, parameter_volatile",
                "Value": 0
              }
            ]
          }
        ]
      },
      "Watchdog": {
        "Enabled": true,
        "Disabled": false,
        "high": 1000000,
        "tooHigh": 5000000
      }
    }
  ]
}
```

**Key Fields:**
- `Name`: Service name (used in parameter tree as `root/Services/{Name}`)
- `Config`: Runtime configuration (login, password, target_url, autoStart, custom fields)
- `Parameters`: Service-specific parameters (automatically placed under `root/Services/{Name}/serviceParameters/`)
- `Watchdog`: Watchdog settings (enabled, thresholds in microseconds)

**Parameter Types:**
- `input`: Client writes, Target reads (buttons, commands)
- `output`: Target writes, client reads (sensor data, status)
- `parameter`: Configuration values
- `parameter_volatile`: **Recommended for client outputs** - frequently changing values written by client

**Important:** Access service parameters via `self.options.get_service_parameter_path`:
```python
button = self.req.getParameter(f"{self.options.get_service_parameter_path}/StartButton").get().value[0]
```

### `package_config.json` - Build Configuration

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

**CRITICAL:** When renaming files or changing structure, update this configuration:
- Rename `mcx-client-app.py` → Update `PYTHON_SCRIPT`
- Change package name → Update `PACKAGE_NAME`

See `deploying/readme.md` for a complete list of configuration options.

## Using the Template

### 1. Basic Application Structure

The template uses the `McxClientApp` base class which handles:

- Connection management to Motorcortex server
- Start/stop control via `enableService` parameter
- State machine integration (optional)
- Automatic watchdog keep-alive
- Error handler for system-level errors

Create your application by inheriting from `McxClientApp`:

```python
from src.mcx_client_app import McxClientApp, McxClientAppConfiguration
import logging

class MyApp(McxClientApp):
    def __init__(self, options: McxClientAppConfiguration):
        super().__init__(options)
        # Initialize instance variables
        self.counter = 0
    
    def startOp(self):
        """Called after connection, before iterate starts"""
        # Setup subscriptions, initialize parameters
        self.req.setParameter(f"{self.options.get_service_parameter_path}/Counter", 0).get()
        logging.info("App initialized")

    def iterate(self):
        """Main application logic - called repeatedly"""
        self.counter += 1
        logging.info(f"Iteration {self.counter}")
        
        # ✅ CRITICAL: Use self.wait() to keep watchdog alive!
        self.wait(1.0)  # Wait with stop signal support

    def onExit(self):
        """Cleanup before disconnecting"""
        logging.info(f"Exiting after {self.counter} iterations")

if __name__ == "__main__":
    config = McxClientAppConfiguration(name="MyApp")
    config.set_config_paths(
        deployed_config="/etc/motorcortex/config/services/services_config.json",
        non_deployed_config="services_config.json"
    )
    config.load_config()
    app = MyApp(config)
    app.run()
```

**Lifecycle Methods:**
1. `__init__()` - Initialize instance variables
2. `startOp()` - Setup after connection (subscriptions, parameters)
3. `iterate()` - Main logic (called repeatedly while running)
4. `onExit()` - Cleanup before disconnect

### 2. Working with Parameters

**Service Parameters vs Configuration:**

- **Service Parameters** (`root/Services/{Name}/serviceParameters/`): Values that **change during runtime** (buttons, setpoints, counters)
- **Configuration** (`Config` section): Values **set once at startup** (connection settings, constants)

**Example:**
```python
# Runtime-adjustable parameter (defined in Parameters section)
{"Name": "MaxSpeed", "Type": "double, input"}
# Access: self.req.getParameter(f"{self.options.get_service_parameter_path}/MaxSpeed")

# Static configuration (defined in Config section)  
{"max_retries": 3, "connection_timeout": 30}
# Access: self.options.max_retries
```

### 3. Subscriptions for Real-Time Updates

Use subscriptions to receive parameter updates efficiently:

```python
import motorcortex

def startOp(self):
    # Subscribe to multiple parameters in one subscription
    self.sensor_sub = self.sub.subscribe(
        [
            "root/Sensors/Temperature",
            "root/Sensors/Pressure"
        ],
        group_alias="sensors",
        frq_divider=100  # Update frequency
    )
    result = self.sensor_sub.get()
    if result and result.status == motorcortex.OK:
        self.sensor_sub.notify(self._onSensorUpdate)

def _onSensorUpdate(self, msg):
    """Callback - runs in subscription thread, keep FAST!"""
    temp = msg[0].value[0]
    pressure = msg[1].value[0]
    # Store values for use in iterate()
    self.temperature.set(temp)
    self.pressure.set(pressure)

def onExit(self):
    if self.sensor_sub:
        self.sensor_sub.unsubscribe()
```

**CRITICAL:** Keep subscription callbacks extremely fast - only extract and store values. Do all processing in `iterate()`.

### 4. Error Handling

Trigger system-level errors at different severity levels:

```python
def startOp(self):
    # Configure error handler
    self.errorHandler.set_subsystem_id(1)
    self.errorHandler.set_acknowledge_callback(self.on_error_acknowledged)

def iterate(self):
    if critical_condition:
        self.errorHandler.trigger_emergency_stop(error_code=5001)
    elif warning_condition:
        self.errorHandler.trigger_warning(error_code=1001)

def on_error_acknowledged(self):
    logging.info("Error acknowledged - resetting")
    # Reset application state
```

### 5. Explore the Examples

Check the `examples/` folder for working implementations:

- **`robot_app.py`** - Control a robot arm with motion programs
- **`start_button.py`** - Use start/stop control with `autoStart`
- **`custom_button.py`** - Create custom GUI controls with subscriptions
- **`error_app.py`** - Error handler with rising edge detection
- **`datalogger.py`** - Data logging with custom configuration

### 6. Local Testing

Test your application locally before deploying:

```bash
python3 mcx-client-app.py
```

Or test with an example:

```bash
python3 examples/robot_app.py
```

The application will:
1. Load configuration from `services_config.json`
2. Connect to the Motorcortex server
3. Wait for `autoStart: true` or manual enable via `enableService` parameter
4. Run your `iterate()` method repeatedly
5. Stop when disabled or interrupted

### 7. Building a Debian Package

Use Docker to build a portable Debian package:

```bash
# Build the Docker image (first time only)
cd deploying
docker build -t mcx-2025-03-37-deb-builder .

# Build your Debian package
cd ..
docker run --rm -v "$PWD:/workspace" -w /workspace \\
    mcx-2025-03-37-deb-builder package_config.json
```

The resulting `.deb` file will be in the `build/` folder.

### 8. Deployment

1. Upload your `.deb` package to the Motorcortex Portal
2. Install it on your target MCX-RTOS system
3. The application will automatically start as a systemd service
4. Control it from the Motorcortex GRID GUI or DESK tool

## Key Features

### Connection Management
- Automatic connection to Motorcortex server via WebSocket
- TLS/SSL support with certificate validation
- Automatic reconnection on connection loss
- Login/password authentication

### Start/Stop Control
- Built-in `enableService` parameter for start/stop control
- `autoStart: true` - starts immediately when service enabled
- `autoStart: false` - waits for manual enable
- Graceful shutdown with cleanup via `onExit()`

### Watchdog Management
- **Automatic watchdog keep-alive** when using `self.wait()` or `self.wait_for()`
- Configurable thresholds (warning and error levels)
- ⚠️ **NEVER use `time.sleep()`** - watchdog will timeout!

### Error Handling
- System-level error triggering at 5 severity levels
- Subsystem ID for error source identification
- Error code tracking for specific conditions
- Acknowledgment callbacks for error recovery

### State Machine Integration (Optional)
- Run only during specific Motorcortex states
- `run_during_states` configuration option
- Automatic state monitoring

### Subscriptions
- Real-time parameter updates via callbacks
- Efficient grouped subscriptions
- Thread-safe value sharing with `ThreadSafeValue`

### Systemd Service
- Automatic startup with Motorcortex server
- Configurable restart behavior
- Proper dependency management

## Advanced Usage

### Using McxClientAppThread

For long-running operations that need independent stopping, use `McxClientAppThread`:

```python
from src.mcx_client_app import McxClientAppThread

class LongRunningApp(McxClientAppThread):
    def iterate(self):
        # Long computation - runs in separate thread
        for i in range(1000):
            self.process_data(i)
            if not self.running.get():  # Check manually in loops
                break
            self.wait(0.01)
```

**When to use:**
- ✅ `McxClientApp`: Simple sequential workflows (recommended default)
- ✅ `McxClientAppThread`: Long-running operations that need immediate stop response

### Custom Configuration

Extend `McxClientAppConfiguration` for custom parameters:

```python
class MyAppConfiguration(McxClientAppConfiguration):
    def __init__(self, log_interval: float = 1.0, log_file: str = "data.json", **kwargs):
        # Set custom attributes BEFORE super().__init__()
        self.log_interval = log_interval
        self.log_file = log_file
        super().__init__(**kwargs)

# In services_config.json Config section:
{
  "Config": {
    "login": "admin",
    "password": "pass",
    "target_url": "wss://192.168.1.100",
    "log_interval": 0.5,
    "log_file": "sensor_data.json"
  }
}

# Access in code:
self.options.log_interval  # 0.5
```

### ChangeDetector for Command Monitoring

Use the built-in `commandWord` parameter with `ChangeDetector` for external commands:

```python
from src.mcx_client_app.ChangeDetector import ChangeDetector

class MyApp(McxClientApp):
    def __init__(self, options):
        super().__init__(options)
        self.command_detector = ChangeDetector()
    
    def startOp(self):
        # Subscribe to commandWord
        self.cmd_sub = self.sub.subscribe(
            [f"{self.options.get_parameter_path}/commandWord"],
            "cmd", frq_divider=10
        ).get()
        self.cmd_sub.notify(lambda msg: self.command_detector._ChangeDetector__value.set(msg[0].value[0]))
    
    def iterate(self):
        # Check for commands (ignore changes TO zero)
        if self.command_detector.has_changed(trigger_on_zero=False):
            cmd = self.command_detector.get_value()
            if cmd == 1:
                self.reset_operation()
            elif cmd == 2:
                self.pause_operation()
            # Acknowledge command
            self.req.setParameter(f"{self.options.get_parameter_path}/commandWord", 0).get()
```

### Custom Service Template

Create your own systemd service template by modifying `deploying/template.service.in` and referencing it in `package_config.json`.

### Multiple Services

Deploy multiple services by adding them to `services_config.json`:

```json
{
  "Services": [
    {"Name": "DataLogger", "Enabled": true, ...},
    {"Name": "RobotController", "Enabled": true, ...}
  ]
}
```

### Custom Dependencies

Add your own Python dependencies by editing `requirements.txt` and rebuilding the package.

## Best Practices

✅ **DO:**
- Use `self.wait()` instead of `time.sleep()` (keeps watchdog alive)
- Keep `iterate()` clean - extract logic into private helper methods
- Use subscriptions instead of polling parameters
- Group related parameters in one subscription for efficiency
- Keep subscription callbacks FAST (only extract and store values)
- Use `parameter_volatile` type for client app outputs
- Document required parameters in docstring
- Unsubscribe in `onExit()`

❌ **DON'T:**
- Use `time.sleep()` - watchdog will timeout!
- Block in subscription callbacks
- Poll parameters in `iterate()` - use subscriptions
- Create custom parameters directly under `root/` - use `root/Services/{Name}/serviceParameters/`
- Use `output` type for values your app writes (use `parameter_volatile`)
- Try to call `setParameter()` on `output` type parameters

## Common Use Cases

- **Automated Testing** - Run test sequences on your Motorcortex application
- **Motion Control** - Execute complex motion profiles for robots or AGVs
- **Data Logging** - Stream data to databases, InfluxDB, or time-series systems
- **Protocol Bridges** - Connect Motorcortex to MQTT, OPC-UA, ROS, or other middlewares
- **Custom Automation** - Implement application-specific behavior and workflows

## Versioning

The template exposes a Pythonic package version. You can access it from code:

```python
from src import mcx_client_app
print(mcx_client_app.__version__)      # e.g. "0.1.0"
# or
print(mcx_client_app.get_version())    # returns the version string
```

The canonical version string is stored in `src/mcx_client_app/_version.py` and the package exposes it at `src/mcx_client_app/__version__`.

## Troubleshooting

### Connection Issues
- Verify `target_url` in `services_config.json` Config section
- Check certificate path (use `/etc/ssl/certs/mcx.cert.pem` on MCX-RTOS, `mcx.cert.crt` locally)
- Ensure Motorcortex server is running and accessible
- Verify login/password credentials

### Service Not Starting
- Check if `autoStart: true` is set in Config section
- Verify `enableService` parameter is enabled
- Check service status: `systemctl status your-service-name`
- View logs: `journalctl -u your-service-name -f`
- Verify configuration file is valid JSON

### Watchdog Timeout Errors
- Replace all `time.sleep()` with `self.wait()`
- Add periodic `self.wait(0.01)` calls in long loops
- Ensure `iterate()` doesn't block for long periods

### Parameter Access Errors
- Use `self.options.get_service_parameter_path` for service parameters
- Verify parameter types match usage (can't write to `output` parameters)
- Check parameter paths in DESK tool or parameter tree
- Ensure parameters are defined in `services_config.json` Parameters section

### Build Issues
- Ensure Docker is installed and running: `docker --version`
- Update `PYTHON_SCRIPT` in `package_config.json` if you renamed files
- Review build logs for specific errors
- Verify all required files are present

## Additional Resources

- [Motorcortex Documentation](https://docs.motorcortex.io/)
- [Python API Reference](https://docs.motorcortex.io/docs/developing-client-applications/python/)
- [Motorcortex Portal](https://motorcortex.io/)

## Support

For issues, questions, or contributions, please refer to the Motorcortex documentation or contact Vectioneer support.
