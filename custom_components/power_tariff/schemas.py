import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import WEEKDAYS

DAY_SCHEMA = vol.Schema({
    vol.Optional("start", default="00:00:00"): cv.time,
    vol.Optional("end", default="23:59:59"): cv.time,
    vol.Optional("weekday", default=""): vol.In(WEEKDAYS),
})

TARIFF_SCHEMA = vol.Schema({
    vol.Required("name", default="dag"): cv.string,
    vol.Required("limit_kwh", default=1000): int,
    vol.Optional("over_limit_acceptance", default=0.0): cv.small_float,
    vol.Optional("over_limit_acceptance_seconds", default=60.0): float,
    vol.Optional("days", default=list()): vol.Any(cv.ensure_list, [DAY_SCHEMA]),
    vol.Optional("enabled", default=True): cv.boolean,
})

DEVICE_SCHEMA = vol.Schema({
    vol.Required("turn_on"): cv.string, # cv.entity_id <-- would be a better check, but lets drop this for now
    vol.Optional("turn_off"): cv.string,
    vol.Optional("priority", default=10): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
    vol.Optional("enabled", default=True): cv.boolean,
    vol.Optional("power_usage"): cv.string,  # some enit where is this possible to get
    vol.Optional("assumed_usage", default=0.0): float,  # Backup if we dont have way to get the device power usage
})
