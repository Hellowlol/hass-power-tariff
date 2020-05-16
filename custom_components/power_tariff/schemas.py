import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import WEEKDAYS

from .validators import validate_date

_LOGGER = logging.getLogger(__name__)

_UNDEF = object()


def vad(value, schema):
    """Helper to create default config and replace them with
       the one that the user has given.
    """

    if isinstance(value, dict):
        # Validate and  convert to the correct type.
        values = schema(value)
        # Create the default values
        defs = schema({})
        # Replace default values with what the user have given.
        defs.update(values)
        _LOGGER.debug("%r", defs)
        return defs

    elif value is None:
        defs = schema({})
        _LOGGER.debug("Value was None %r", defs)
        return defs

    elif value is _UNDEF:
        defs = schema({})
        _LOGGER.debug("_UNDEF %r", defs)
        return defs


TIME_SCHEMA = vol.Schema(
    {
        vol.Required("start", default="00:00:00"): cv.time,
        vol.Required("end", default="23:59:59"): cv.time,
    }
)

DATE_SCHEMA = vol.Schema(
    {
        vol.Required("start", default="01.01"): validate_date,
        vol.Required("end", default="31.12"): validate_date,
    }
)


DAY_SCHEMA = vol.Schema(
    {
        vol.Optional("date", default={}): vol.All(
            lambda value: vad(value, DATE_SCHEMA)
        ),
        vol.Optional("time", default={}): vol.All(
            lambda value: vad(value, TIME_SCHEMA)
        ),
        vol.Optional("weekday", default=WEEKDAYS): vol.All(cv.ensure_list, WEEKDAYS),
    }
)

TARIFF_SCHEMA = vol.Schema(
    {
        vol.Required("name", default="dag"): cv.string,
        vol.Required("limit_kwh", default=1000): int,
        vol.Optional("over_limit_acceptance", default=0.0): cv.small_float,
        vol.Optional("over_limit_acceptance_seconds", default=60.0): float,
        #  The restrictions can be completely omitted and default config is still created.
        vol.Optional("restrictions"): vol.All(lambda value: vad(value, DAY_SCHEMA)),
        vol.Optional("enabled", default=True): cv.boolean,
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(
            "turn_on"
        ): cv.string,  # cv.entity_id <-- would be a better check, but lets drop this for now
        vol.Optional("turn_off"): cv.string,
        vol.Optional("priority", default=10): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
        vol.Optional("enabled", default=True): cv.boolean,
        vol.Optional(
            "power_usage"
        ): cv.string,  # some entity where is this possible to get
        vol.Optional(
            "assumed_usage", default=0.0
        ): float,  # Backup if we dont have way to get the device power usage
    }
)
