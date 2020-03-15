
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

TIME_SCHEMA = {vol.Optional("weekdays"): vol.All(cv.ensure_list, cv.string)}

TARIFF_SCHEMA = {
        vol.Required(CONF_NAME, default='dag'): cv.string,
        vol.Required("limit_kwh", default=""): int,
        vol.Optional("over_limit_acceptance", default=0.0): float,
        vol.Optional("over_limit_acceptance_seconds", default=60): float # float

}

DEVICE_SCHEMA = {
    vol.Required("entity"): cv.string,
    vol.Optional("priority", default=10): int,
    vol.Optional("enabled", default=True): bool,
    vol.Optional("power_usage"): cv.string, # some enit where is this possible to get
    vol.Optional("assumed_usage"): cv.string # Backup if we dont have way to get the device power usage
}

