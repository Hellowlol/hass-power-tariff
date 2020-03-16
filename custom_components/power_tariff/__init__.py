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
from homeassistant.helpers.event import track_state_change
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
    pc = PowerController(hass, config)
    devs = []
    tariffs = []
    for device in config.get("devices"):
        dev = Device(hass, device)
        devs.append(dev)

    for tariff in config.get("tariffs"):
        tar = Tariff(tariff)
        tariffs.append(tar)


    def cb(*args, **kwargs):
        # We don't really care about the cb, it just kick off everthing.
        pc.update()

    pc.add_device(devs)
    pc.add_tariff(tariffs)
    hass.data[DOMAIN] = pc
    track_state_change(hass, entity_ids=config.get("monitor_entity"), action=cb)

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
        """validate if the tariff is valid (active)"""
        _LOGGER.info("the tariff is valid")
        return True


    @property
    def tariff_limit(self):
        """ """
        return self.limit_kwh * (
            1 + self.over_limit_acceptance
        )


class Device:
    """Devices"""

    def __init__(self, hass, settings):
        self.modified = None
        self.hass = hass
        self.enabled = settings.get("enabled")
        self.priority = settings.get("priority")
        # Enitity to get the power usage
        self.power_usage = settings.get("power_usage")
        self.assumed_usage = settings.get("assumed_usage")
        self.turn_on_entity = settings.get("turn_on")
        self.turn_off_entity = settings.get("turn_off")

        if not self.turn_off_entity:
            self.turn_off_entity = self.turn_on_entity

    #@property
    def get_power_usage(self):
        try:
            pw = self.hass.states.get(self.power_usage)
        except AttributeError:
            pw = None

        if pw is None:
            _LOGGER.info(
                "%s dont have a power_usage, using assumed_usage %s",
                self.power_usage,
                self.assumed_usage,
            )
            pw = self.assumed_usage
        else:
            pw = pw.state

        return float(pw)

    def _turn(self, mode=False):


        if mode is True:
            m = SERVICE_TURN_ON
            entity_id = self.turn_on_entity
        else:
            m = SERVICE_TURN_OFF
            entity_id = self.turn_off_entity

        self.modified = mode

        # There must be a helper for this..
        domain = entity_id.split(".")[0]
        # A scene can only turn on, never off
        if domain == "scene":
            m = SERVICE_TURN_ON

        data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
        # Need to fix the domain.
        _LOGGER.info("tried to %s %s %r", entity_id, m, data)

        #self.hass.services.call(domain, m, data)

    def toggle(self):
        if self.modified is None:
            _LOGGER.info("cant toggle is the obj wasnt controlled.")
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
            self.tariffs.extend(tariff)
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
        """There must be a better way to get it."""
        state = self.hass.states.get(self.settings.get("monitor_entity"))
        _LOGGER.info("%r", state)
        try:
            return int(state.state)
        except ValueError:
            # unknown state comes to mind.
            return 0

    def pick_minimal_power_reduction(self):
        """Turns off devices so we dont exceed the tariff limits."""
        _LOGGER.info("Checking what devices we can turn off")
        #devs = defaultdict(dict)
        power_reduced_kwh = 0
        devs = []

        current_power_usage = self.current_power_usage

        for device in sorted(self.devices, key=attrgetter("priority")):
            # Make sure we dont do anything
            # to disabled devices.
            if device.enabled is False:
                _LOGGER.info("Device %s is not enabled", device)
                continue

            power_usage_state = device.get_power_usage()
            power_reduced_kwh += power_usage_state
            current_power_usage -= power_usage_state
            devs.append(device)

            if current_power_usage <= self.current_tariff.tariff_limit:
                _LOGGER.info("Reached the limit..")
                break

        if devs:
            for dev in devs:
                dev.turn_off()

    def should_reduce_power(self):
        _LOGGER.info("current usage %s tariff limit %s", self.current_power_usage, self.current_tariff.tariff_limit)
        if self.current_power_usage > self.current_tariff.tariff_limit:
            if self.first_over_limit is None:
                self.first_over_limit = time.time()


            if self.current_tariff.over_limit_acceptance_seconds > 0:
                if time.time() - self.first_over_limit > self.current_tariff.over_limit_acceptance_seconds:
                    _LOGGER.info("been over limit for more then over_limit_acceptance_seconds", self.current_tariff.over_limit_acceptance_seconds)
                    self.first_over_limit = None

                    return True
                else:
                    _LOGGER.info("We are over the limit")
                    return False
            else:
                return True
        else:
            return False

    def check_if_we_can_turn_on_devices(self):
        """Turn off any devices we can without exceeding the tariff"""
        # to turn on we dont allow temp usage to exceed tariff.
        for device in self.devices:
            if device.modified is not None:
                if device.modified is False:
                    device.turn_on()

    def update(self, power_usage=None):
        _LOGGER.info("called update")

        if self.current_tariff is None:
            _LOGGER.info("No tariff exists")
            # Just grab one...
            self._current_tariff = self.tariffs[0]

        if self.current_tariff.valid():
            reduce_power = self.should_reduce_power()
            _LOGGER.info("should_reduce_power %s", reduce_power)
            if reduce_power:
                self.pick_minimal_power_reduction()
            else:
                self.check_if_we_can_turn_on_devices()
