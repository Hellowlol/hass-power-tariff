"""Support for power tariff."""
import logging
import time
from collections import defaultdict
from operator import attrgetter, itemgetter

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.const import (ATTR_ENTITY_ID, ATTR_TEMPERATURE,
                                 CONF_PASSWORD, CONF_USERNAME,
                                 ENTITY_MATCH_ALL, SERVICE_TURN_OFF,
                                 SERVICE_TURN_ON)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DOMAIN
from .schemas import DEVICE_SCHEMA, TARIFF_SCHEMA, TIME_SCHEMA

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("monitor_entity"): cv.string,
                vol.Optional("tariffs"): vol.All(cv.ensure_list, [TARIFF_SCHEMA]),
                vol.Optional("devices"): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config) -> bool:
    """Set up using yaml config file."""
    _LOGGER.info("Setup zomg!")
    config = config[DOMAIN]
    pc = PowerController(hass, config[DOMAIN])
    devs = []
    tariffs = []
    for device in config.get("devices"):
        dev = Device(device)
        devs.append(dev)

    for tariff in config.get("tariffs"):
        tar = Tariff(tariff)
        tariffs.append(tar)

    pc.add_device(devs)
    pc.add_tariff(tariffs)

    hass.data[DOMAIN] = pc
    return True


class Tariff:
    def __init__(self, settings):
        self.enabled = settings.get("enabled")
        self.priority = settings.get("priority")
        self.limit_kwh = settings.get("limit_kwh")
        self.over_limit_acceptance = settings.get("over_limit_acceptance")
        self.over_limit_acceptance_seconds = settings.get(
            "over_limit_acceptance_seconds"
        )

    def valid(self):
        return True


class Device:
    """Devices"""

    def __init__(self, hass, settings):
        self.modified = None
        self._hass = hass
        self.enabled = settings.get("enabled")
        # Enitity to turn on and off.
        self.entity_id = settings.get("entity_id")
        # Enitity to get the power usage
        self.power_usage = settings.get("power_usage")
        self.assumed_usage = settings.get("assumed_usage")

    @property
    def get_power_usage(self):
        pw = self.hass.state.get(self.power_usage)
        if pw is None:
            _LOGGER.info(
                "%s dont have a power_usage, using assumed_usage %s",
                self.entity_id,
                self.assumed_usage,
            )
            pw = self.assumed_usage

        return pw

    def _turn(self, mode=SERVICE_TURN_ON):
        if mode is True:
            m = SERVICE_TURN_ON
        else:
            m = SERVICE_TURN_OFF

        data = {ATTR_ENTITY_ID: self.entity_id} if entity_id else {}
        # Need to fix the domain.
        self.hass.services.call(DOMAIN, m, data)

    def toggle(self):
        value = not self.modified
        return self._turn(value)

    def turn_on(self):
        return self._turn(True)

    def turn_off(self):
        return self._turn(False)


class PowerController:
    def __init__(self, hass, settings):
        _LOGGER.info("%r", settings)
        self.hass = hass
        self.settings = settings
        self._controlled_thing = {}
        self._current_tariff = None
        self.over_limit_for = 0
        self.first_over_limit = None
        self.devices = []
        self.tariffs = []

    def add_device(self, device):
        if isinstance(device, list):
            self.devices.extend(device)
        else:
            self.devices.append(device)

    def add_tariff(self, tariff):
        if isinstance(tariff, list):
            self.tariff.extend(tariff)
        else:
            self.tariffs.append(tariff)

    @property
    def current_tariff(self):
        return self._current_tariff

    def check_tariff(self):
        """Check if we have a valid tariff we should use."""
        for tariff in self.tariffs:
            if tariff.enabled:
                self._current_tariff = tariff
        else:
            _LOGGER.info("no valid tariff")

    @property
    def current_power_usage(self):
        return self.hass.state.get(self.settings.get("monitor_entity"))

    @property
    def tariff_limit(self):
        return self.current_tariff.limit_kwh * (
            1 + self.current_tariff.over_limit_acceptance
        )

    def pick_minimal_power_reduction(self):
        """Turns off devices so we dont exceed the tariff limits

        """
        devs = defaultdict(dict)
        power_reduced_kwh = 0
        devs = []

        current_power_usage = self.current_power_usage

        for device in sorted(self.devices, key=itemgetter("priority")):
            # Make sure we dont do anything
            # to disabled devices.
            if device.enabled is False:
                _LOGGER.info("Device %s is not enabled", device)
                continue

            power_usage_state = device.get_power_usage()
            power_reduced_kwh += power_usage_state
            current_power_usage -= power_usage_state
            devs.append(device)

            if current_power_usage <= self.tariff_limit:
                _LOGGER.info("Reached the limit..")
                break

        if devs:
            for dev in devs:
                dev.turn_off()

    def should_reduce_power(self):
        if self.current_power_usage > self.tariff_limit:
            if self.first_over_limit is None:
                self.first_over_limit = time.time()

            if (
                self.current_tariff.over_limit_acceptance_seconds
                and time.time() - self.first_over_limit
                > self.current_tariff.over_limit_acceptance_seconds
            ):
                self.first_over_limit = None
                return True
            else:
                return False
        else:
            return False

    def check_if_we_can_turn_on_devices(self):
        """Turn off any devices we can without exceeding the tariff"""
        # to turn on we dont allow temp usage to exceed tariff.
        for device in self.devices:
            if device.modified is not None:
                pass

    def update(self):
        if self.check_tariff():
            if self.should_reduce_power():
                self.pick_minimal_power_reduction()
            else:
                self.check_if_we_can_turn_on_devices()
