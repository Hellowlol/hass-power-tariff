"""Support for power tariff."""
import logging
import time
from operator import attrgetter

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.const import (ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_START,
                                 SERVICE_TOGGLE, SERVICE_TURN_OFF,
                                 SERVICE_TURN_ON)
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers.event import track_state_change
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DOMAIN
from .exceptions import NoValidTariff
from .schemas import DEVICE_SCHEMA, TARIFF_SCHEMA

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("monitor_entity"): cv.entity_id,
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

    def ha_ready_cb(event):
        pc.ready = True

    pc.add_device(devs)
    pc.add_tariff(tariffs)
    hass.data[DOMAIN] = pc

    hass.bus.listen(EVENT_HOMEASSISTANT_START, ha_ready_cb)
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
        self.days = settings.get("days")

    def valid(self):
        """validate if the tariff is valid (active)"""
        now = dt_util.now()

        if not len(self.days):
            _LOGGER.debug("No days are added, as result its always valid..")
            return True

        else:
            for day in self.days:
                if day["weekday"] == now.strftime("%a").lower():
                    _LOGGER.debug("It's the corrent day")
                    if day["start"] < now.time() and now.time() < day["end"]:
                        _LOGGER.debug(
                            "now %s between start %s and end %s",
                            now.time(),
                            day["start"],
                            day["end"],
                        )
                        return True
                    else:
                        continue
                else:
                    _LOGGER.debug(
                        "today is not %s %s", day["weekday"], now.strftime("%a")
                    )
                    continue

        return False

    @property
    def tariff_limit(self):
        """ """
        return self.limit_kwh * (1 + self.over_limit_acceptance)


class Device:
    """Represent a device that power controller can manage."""

    def __init__(self, hass, settings):
        # Last action
        self.action = None
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

    def get_power_usage(self):
        try:
            pw = self.hass.states.get(self.power_usage)
        except AttributeError:
            pw = None

        if pw is None:
            _LOGGER.debug(
                "%s dont have a power_usage, using assumed_usage %s",
                self.power_usage,
                self.assumed_usage,
            )
            pw = self.assumed_usage
        else:
            pw = pw.state

        return float(pw)

    def _turn(self, mode=False):
        """Helper to turn off on on a device"""

        # Some where we need to check if the device still has the same action as before
        # We want a user to able to manually turning on/off the device
        # and if thats done we should touch the device for some periode of time.
        # Maybe we needed a grace periode for some kind, so we dont turn off the hotplate
        # during dinner. :D

        if mode is True:
            m = SERVICE_TURN_ON
            entity_id = self.turn_on_entity
        else:
            m = SERVICE_TURN_OFF
            entity_id = self.turn_off_entity

        domain = "homeassistant"

        service_data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

        _LOGGER.debug(
            "tried to called with domain %s service %s %r", domain, m, service_data
        )
        try:
            self.hass.services.call(domain, m, service_data)
        except ServiceNotFound:
            _LOGGER.info("Maybe Service wasnt ready yet")
            return

        self.action = mode

    def toggle(self):
        # FIX ME
        t = SERVICE_TOGGLE
        if self.modified is None:
            _LOGGER.info("Can't toggle and the device hasnt been controlled.")
        value = not self.action
        return self._turn(value)

    def turn_on(self):
        return self._turn(True)

    def turn_off(self):
        return self._turn(False)

    def reset(self):
        self.action = None


class PowerController:
    def __init__(self, hass, settings):
        _LOGGER.debug("%r", settings)
        self.hass = hass
        self.settings = settings
        self._current_tariff = None
        self.first_over_limit = None
        self.devices = []
        self.tariffs = []
        self.ready = False

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
            if tariff.enabled and tariff.valid():
                self._current_tariff = tariff
                break
        else:
            raise NoValidTariff

    @property
    def current_power_usage(self):
        """There must be a better way to get it."""
        state = self.hass.states.get(self.settings.get("monitor_entity"))
        try:
            return int(state.state)
        except ValueError:
            # unknown state comes to mind.
            return 0

    def pick_minimal_power_reduction(self):
        """Turns off devices so we dont exceed the tariff limits."""
        _LOGGER.debug("Checking what devices we can turn off")
        power_reduced_kwh = 0
        devs = []

        current_power_usage = self.current_power_usage

        for device in sorted(self.devices, key=attrgetter("priority")):
            # Make sure we dont do anything
            # to disabled devices.
            if device.enabled is False:
                _LOGGER.info("Device %s is not enabled", device)
                continue

            # Just to we dont spam the same command over and over.
            # We also need to be able to handle that ha user has turned something on.
            if device.action is not None:
                _LOGGER.debug(
                    "Device %r alread has action %s skipping it.", device, device.action
                )
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
        if self.current_power_usage > self.current_tariff.tariff_limit:
            if self.first_over_limit is None:
                self.first_over_limit = time.time()

            if self.current_tariff.over_limit_acceptance_seconds > 0:
                if (
                    time.time() - self.first_over_limit
                    > self.current_tariff.over_limit_acceptance_seconds
                ):
                    _LOGGER.debug(
                        "Been over limit for more then over_limit_acceptance_seconds %s",
                        self.current_tariff.over_limit_acceptance_seconds,
                    )
                    self.first_over_limit = None
                    return True
                else:
                    _LOGGER.info("We are over the limit, but we havnt been over enough")
                    return False
            else:
                return True
        else:
            return False

    def check_if_we_can_turn_on_devices(self):
        """Turn off any devices we can without exceeding the tariff"""
        # to turn on we dont allow temp usage to exceed tariff.
        for device in self.devices:
            if device.action == SERVICE_TURN_OFF:
                _LOGGER.debug(
                    "Device %r has been turned off by power controller, try to turn it on",
                    device,
                )
                device.turn_on()

    def update(self, power_usage=None):
        """Main method that really handles most of the work."""
        if self.ready is False:
            return

        self.check_tariff()

        if self.current_tariff.valid():
            reduce_power = self.should_reduce_power()
            _LOGGER.debug("should_reduce_power %s", reduce_power)
            if reduce_power:
                self.pick_minimal_power_reduction()
            else:
                self.check_if_we_can_turn_on_devices()

    # def update(self):
    #    # self.hass.helpers.entity_registry.async_get_registry()
    #    for ent in self.hass.states.all():
    #        pass
