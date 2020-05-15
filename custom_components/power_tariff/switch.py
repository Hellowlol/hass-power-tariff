"""Devices as switches"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import (ATTR_ENTITY_ID, SERVICE_TURN_OFF,
                                 SERVICE_TURN_ON, STATE_OFF, STATE_ON,
                                 STATE_PROBLEM, STATE_UNAVAILABLE,
                                 STATE_UNKNOWN)
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers.config_validation import (PLATFORM_SCHEMA,
                                                     PLATFORM_SCHEMA_BASE)

from .const import DOMAIN, POWER_ATTRS
from .utils import get_entity_object

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


STATE_AS_ON = (STATE_ON,)
STATE_AS_OFF = (STATE_OFF,)


class PowerDevice(SwitchDevice):
    """Represent a device that power controller can manage."""

    def __init__(self, hass, pc, settings):
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
        self._proxy_device_off = None
        self._proxy_device_on = None

        if not self.turn_off_entity:
            self.turn_off_entity = self.turn_on_entity

    def get_power_usage(self):

        if self.power_usage is None:
            for attr in POWER_ATTRS:
                state = self.hass.states.get(self.turn_on)

                if state and state.attributes.get(attr) is not None:
                    _LOGGER.debug("Using attribute %s on %s to get the power usage", attr, self.turn_on)
                    return float(state.attributes.get(attr))

            return float(self.assumed_usage)

        else:
            try:
                return float(self.hass.states.get(self.power_usage))
            except (AttributeError, TypeError):
                _LOGGER.debug("Failed to get the power usage from %s, using assumed usage", self.power_usage)
                return float(self.assumed_usage)


    async def _turn(self, mode=False):
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

        act = self.is_proxy_device_on()
        if self.action is not None and d[self.action] is not act:
            _LOGGER.info("Proxy device has changed status without power controller doing it (fx manually pressed the button, a automation or something), not doing anything.")
            return

        if mode is True:
            m = SERVICE_TURN_ON
            entity_id = self.turn_on_entity
        else:
            m = SERVICE_TURN_OFF
            entity_id = self.turn_off_entity

        domain = "homeassistant"

        service_data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

        _LOGGER.info(
            "tried to called with domain %s service %s %r", domain, m, service_data
        )
        try:
            await self.hass.services.async_call(domain, m, service_data)
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

    async def proxy_turn_off(self):
        return await self._turn(False)

    async def proxy_turn_on(self):
        return await self._turn(True)

    def _proxy_ok(self, proxy):
        state = self.hass.states.get(proxy.entity_id)
        if state is not None:
            if state.state in (STATE_PROBLEM, STATE_UNAVAILABLE):
                _LOGGER.info("%s has state %s defaulting to False", proxy.entity_id, state.state)
                return False

        if hasattr(proxy, "is_on"):
            return proxy.is_on
        else:
            return False

    def is_proxy_device_on(self):
        if self._proxy_device_on is None:
            found = get_entity_object(self.hass, self.turn_on_entity)
            if found:
                self._proxy_device_on = found

        if self._proxy_device_on is not None:
            return self._proxy_ok(self._proxy_device_on) is True
        return False

    def is_proxy_device_off(self):
        if self._proxy_device_off is None:
            found = get_entity_object(self.hass, self.turn_off_entity)
            if found:
                self._proxy_device_off = found

        if self._proxy_device_off is not None:
            return self._proxy_ok(self._proxy_device_off) is False
        return False

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

    @property
    def state(self):
        return STATE_ON if bool(self.enabled) else STATE_OFF
