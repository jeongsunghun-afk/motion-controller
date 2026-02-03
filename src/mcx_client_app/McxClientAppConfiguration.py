import logging
import os
import json
from .state_def import State


def load_config_json(path: str, name: str) -> dict:
    """
    Load and validate configuration JSON from `path`.

    Args:
        path (str): Path to the configuration JSON file.
        name (str): Name of the service to extract configuration for.

    Returns:
        dict: Configuration dictionary for the specified service.
    """
    assert path is not None, "Configuration path must be provided"
    if not os.path.exists(path):
        raise AssertionError(f"[ERROR] Configuration file not found: {path}")

    with open(path, 'r') as f:
        data = json.load(f)

    services_data = data.get("Services", [])
    if services_data is None or type(services_data) is not list or len(services_data) == 0:
        raise ValueError(f"[ERROR] No service data found in deployed configuration file: {path}")

    matched = None
    for service in services_data:
        if service.get("Name", "") == name:
            matched = service
            break
    else:
        raise ValueError(f"[ERROR] No service with name '{name}' found in deployed configuration file: {path}")

    config_data = matched.get("Config", {}) if matched is not None else {}

    if not isinstance(config_data, dict):
        raise ValueError(f"[ERROR] Invalid configuration format in {path}; expected object/dict.")

    return config_data

class McxClientAppConfiguration:
    """
    Configuration options for McxClientApp.

    Attributes:
        name (str): Name of the client application.
        login (str): Username for authenticating with the Motorcortex server.
        password (str): Password for authenticating with the Motorcortex server.
        target_url (str): Local Development WebSocket URL of the Motorcortex server (e.g., 'wss://localhost').
            This is the endpoint used to establish the connection.
        target_url_deployed (str): Deployed WebSocket URL of the Motorcortex server (default: 'wss://localhost').
            This is the endpoint used when the application is deployed on a system.
        cert (str): Local Development path to the SSL certificate file for secure connection (e.g., 'mcx.cert.crt').
            Required for encrypted communication with the server. This is only used with local development (Not deployed)
        cert_deployed (str): Deployed path to the SSL certificate file for secure connection (default: '/etc/ssl/certs/mcx.cert.pem').
            Required for encrypted communication with the server. This is only used when deployed on a system with the certificate installed.
        statecmd_param (str): Parameter path for sending state commands to the server (default: 'root/Logic/stateCommand').
            Used to control the robot or system state.
        state_param (str): Parameter path for reading the current state from the server (default: 'root/Logic/state').
            Used to monitor the robot or system state.
        run_during_states (list[State]|None): List of allowed states during which the iterate() method can run (default None).
            If the system is not in one of these states, the iterate() method will not execute.
            If empty or None, the iterate() method can run in any state.
        autoStart (bool): Whether the application should start automatically upon connection or wait for `disable` to be turned off by hand (default: True).
        enable_watchdog (bool): Whether to enable the watchdog functionality (default: True).
    
    Note:
        When inheriting from this class, ensure to call super().__init__(**kwargs) after initialising the class parameters. For example,
            class CustomOptions(McxClientAppConfiguration):
                def __init__(self, custom_param: str = "default", **kwargs):
                    self.custom_param = custom_param
                    super().__init__(**kwargs)
    
    """
    def __init__(
        self,
        name: str,
        login: str | None = None,
        password: str | None = None,
        target_url: str = "wss://localhost",
        target_url_deployed: str = "wss://localhost",
        cert: str = "mcx.cert.crt",
        cert_deployed: str = "/etc/ssl/certs/mcx.cert.pem",
        statecmd_param: str | None = "root/Logic/stateCommand",
        state_param: str | None = "root/Logic/state",
        run_during_states: list = None,
        autoStart: bool = True,
        enable_watchdog: bool = True,
        **kwargs
    ) -> None:
        self.name = name
        self.login = login
        self.password = password
        self.target_url = target_url
        self.target_url_deployed = target_url_deployed
        self.cert = cert
        self.cert_deployed = cert_deployed
        self.statecmd_param = statecmd_param
        self.state_param = state_param
        self._run_during_states = State.list_from(run_during_states)
        self.autoStart = autoStart
        self.enable_watchdog = enable_watchdog
        
        self.deployed_config: str = "/etc/motorcortex/config/services/services_config.json"
        self.non_deployed_config: str | None = None

        for key, value in kwargs.items():
            setattr(self, key, value)
            
        self.__has_config = False

    def as_dict(self) -> dict:
        result = dict(self.__dict__)
        # Convert enums to names for serialization
        result["run_during_states"] = [state.name for state in self._run_during_states]
        result.pop('_McxClientAppConfiguration__deployed', None)
        return result

    def __str__(self) -> str:
        return str(self.as_dict())
    
    def load_config(self) -> None:
        """
        Load configuration from the set config paths.
        
        Raises:
            AssertionError: If configuration file is not found.
            ValueError: If configuration format is invalid.
        """
        if self.is_deployed:
            config_file = self.deployed_config
        else: 
            config_file = self.non_deployed_config
        
        config_data = load_config_json(config_file, name=self.name)
        for key, value in config_data.items():
            if key == "run_during_states":
                self._run_during_states = State.list_from(value)
            elif hasattr(self, key):
                setattr(self, key, value)
                        
        self.__has_config = True
        logging.info(f"Configuration loaded from {'deployed' if self.is_deployed else 'non-deployed'} config file: {config_file}")
        logging.debug(f"Configuration loaded: {self}")
        
    def set_config_paths(self, deployed_config: str | None = None, non_deployed_config: str | None = None) -> None:
        """
        Set the configuration file paths for deployed and non-deployed environments.
        
        It is recommended to use for the deployed configuration a path like: `/etc/motorcortex/config/services/mcx_client_app.json`
        This means it will be in line with other motorcortex services and can be managed centrally from the portal. The folder to which Motorcortex portal will deploy config to is `/etc/motorcortex/config/`. Thus using a subfolder `services/` is a good practice to streamline the deployment on Motorcortex controllers.
        
        Args:
            deployed_config (str | None): Path to the configuration file used when deployed. (CANNOT be None when deployed)
            non_deployed_config (str | None): Path to the configuration file used when not deployed.
        """
        if deployed_config is not None:
            self.deployed_config = deployed_config
        if non_deployed_config is not None:
            self.non_deployed_config = non_deployed_config
                        
    @property
    def has_config(self) -> bool:
        """Check if configuration has been set.

        Returns:
            bool: True if configuration has been set, False otherwise.
        """
        return self.__has_config
        
    @property
    def is_deployed(self) -> bool:
        """Check if the application is running in a deployed environment.
        
        Looks for the 'DEPLOYED' environment variable.
        
        Returns:
            bool: True if deployed, False otherwise.
        """
        return os.environ.get("DEPLOYED", False) is not False
    
    @property
    def certificate(self) -> str:
        if self.is_deployed:
            return self.cert_deployed
        return self.cert

    @property
    def ip_address(self) -> str:
        if self.is_deployed:
            return self.target_url_deployed
        return self.target_url
    
    @property
    def run_during_states(self) -> list:
        return self._run_during_states

    @run_during_states.setter
    def run_during_states(self, value):
        self._run_during_states = State.list_from(value)

    @property
    def allowed_states(self) -> list:
        return self._run_during_states
    
    @property
    def get_parameter_path(self)-> str:
        """Get the parameter path root for the service"""
        return f"root/Services/{self.name}"