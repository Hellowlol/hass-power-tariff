"""Devices as switches"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (ATTR_ENTITY_ID, SERVICE_TOGGLE,
                                 SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON)
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA, PLATFORM_SCHEMA_BASE)

from .const import DOMAIN
from .utils import get_entity_object

#SCAN_INTERVAL = timedelta(seconds=10)
_LOGGER = logging.getLogger(__name__)



async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):  # pylint: disable=unused-argument
    pc = hass.data[DOMAIN]
    devices = []
    for dev in discovery_info:
        devices.append(PowerDevice(hass, pc, dev))

    async_add_entities(devices, False)
    pc.add_device(devices)


class PowerDevice(SwitchDevice):
    """Represent a device that power controller can manage."""

    def __init__(self, hass, pc, settings):
        _LOGGER.info("inside PowerDevice __init__")
        _LOGGER.info("hass: %r", hass)
        _LOGGER.info("pc: %r", pc)
        _LOGGER.info("settings %r", settings)
        # Last action
        self.action = None
        self.hass = hass
        self.pc = pc
        self.priority = settings.get("priority")
        # Enitity to get the power usage
        self.power_usage = settings.get("power_usage")
        self.assumed_usage = settings.get("assumed_usage")
        self.turn_on_entity = settings.get("turn_on")
        self.turn_off_entity = settings.get("turn_off")
        self._enabled = settings.get("enabled")
        self._proxy_device = None

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

        d = {"on": True,
             "off": False,
             "turn_off": False,
             "turn_on": True}

        if self.action is not None and d[self.action] is not self.is_proxy_device_on():
            _LOGGER.info("Proxy device has changed status without power controller, not doing anything.")
            return

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

        self.action = m

    def turn_on(self):
        """Turn on monitoring of this device"""
        self._enabled = True

    def turn_off(self):
        """Turn off monitoring of this device"""
        self._enabled = False

    def proxy_turn_off(self):
        return self._turn(False)

    def proxy_turn_on(self):
        return self._turn(False)

    def is_proxy_device(self, entity_id):
        obj = get_entity_object(self.hass, entity_id)

        if obj is not None:
            if hasattr(obj, "is_on"):
                return obj.is_on
            else:
                _LOGGER.warning("%s has no is_on", self.turn_on_entity)
                return False

        return False

    def is_proxy_device_on(self):
        return self.is_proxy_device(self.turn_on_entity) is True

    def is_proxy_device_off(self):
        return self.is_proxy_device(self.turn_off_entity) is False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"priority": self.priority,
                "represent": self.turn_on_entity,
                "power_usage": self.get_power_usage(),
                "is_on": self.is_on}

    @property
    def name(self):
        return f"{DOMAIN}_{self.turn_on_entity}".replace('.', '_')

    @property
    def is_on(self):
        return bool(self._enabled)
