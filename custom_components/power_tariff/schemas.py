import homeassistant.helpers.config_validation as cv
import voluptuous as vol

TIME_SCHEMA = {vol.Optional("weekdays"): vol.All(cv.ensure_list, cv.string)}

TARIFF_SCHEMA = {
    vol.Required("name", default="dag"): cv.string,
    vol.Required("limit_kwh", default=1000): int,
    vol.Optional("over_limit_acceptance", default=0.0): float,
    vol.Optional("over_limit_acceptance_seconds", default=60): float,  # float
}

DEVICE_SCHEMA = {
    vol.Required("entity_id"): cv.string,
    vol.Optional("priority", default=10): int,
    vol.Optional("enabled", default=True): bool,
    vol.Optional("power_usage"): cv.string,  # some enit where is this possible to get
    vol.Optional("assumed_usage", default=0.0): float,  # Backup if we dont have way to get the device power usage
}
