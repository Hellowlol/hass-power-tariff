"""Support for power tariff."""
import logging

from operator import itemgetter, attrgetter


import voluptuous as vol
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME
)



from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)



from .const import DOMAIN
from .schemas import TIME_SCHEMA, TARIFF_SCHEMA, DEVICE_SCHEMA

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required("monitor_entity"): cv.string,
        vol.Optional("tariffs"): vol.All(cv.ensure_list, [TARIFF_SCHEMA]),
        vol.Optional("devices"): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),

    })
}, extra=vol.ALLOW_EXTRA)




class PowerController():
    def __init__(self, hass, settings):
        self.hass = hass
        self.settings = settings
        self._controlled_thing = {}
        self.current_tariff = None
        self.over_limit_for = 0
        self.first_over_limit = None
    

    def check_tariff(self):
        """Check if we have a valid tariff we should use."""
        return True

    @property
    def current_power_usage(self):
        return self.hass.state.get(self.settings.get("monitor_entity"))

    @property
    def tariff_limit(self):
        return self.current_tariff.get("limit_kwh") * (1 + self.current_tariff.get("over_limit_acceptance", 0)

    def pick_minimal_power_reduction(self):
        """Turns off devices so we dont exceed the tariff limits
        
        """
        devs = defaultdict(dict)
        power_reduced_kwh = 0

        current_power_usage = self.current_power_usage

        for device in sorted(self.devices, key=itemgetter("priority")):
            # Make sure we dont do anything
            # to disabled devices.
            if device.enabled is False:
                _LOGGER.info("Device %s is not enabled", device)
                continue

            power_usage_state = self.hass.state.get(device.power_usage)
            if power_usage_state is None:
                # this device has no power info, so lets see if can use assumed power.
                power_usage_state = device.assumed_usage
                _LOGGER.info("Device dont have a power_usage_state using assumed power %s", power_usage_state)
            power_reduced_kwh += power_usage_state
            current_power_usage =- power_usage_state
            devs[device.entity_id] = {"power": power_usage_state, "mode": "off"}

            if current_power_usage <= self.tariff_limit:
                _LOGGER.info("Reached the limit..")
                break
        
        if devs:
            self._controlled_thing.update(devs)
            for d in devs:
                pass
                self.control_device(d)
        
    def should_reduce_power(self):
        tariff_limit = self.current_tariff.get("limit_kwh") * (1 + self.current_tariff.get("over_limit_acceptance", 0)
        if self.current_power_usage >= tariff_limit:
            if self.first_over_limit is None:
                self.first_over_limit = time.time()
            
            if (self.current_tariff.get('over_limit_acceptance_seconds') 
                and time.time() - self.first_over_limit > self.current_tariff.get('over_limit_acceptance_seconds')):
                self.first_over_limit = None
                return True
            else:
                return False
   
        else:
            return False
    

    def check_if_we_can_turn_on_devices(self):
        """Turn off any devices we can without exceeding the tariff"""
        # to turn on we dont allow temp usage to exceed tariff.
        for devices in self.devices:
            if device.entity_id in self._controlled_thing:
                if self._controlled_thing[device.entity_id] is False:
                    # this is something that we

    
    def update(self):
        if self.check_tariff():
            if self.should_reduce_power():
                self.pick_minimal_power_reduction()
            else:
                self.check_if_we_can_turn_on_devices()

    def control_device(self, device, mode=True):
        """Control a device by turning it off or on."""

        if mode is True:
            m = SERVICE_TURN_ON
        else:
            m = SERVICE_TURN_OFF

        data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
        self.hass.services.call(DOMAIN, m, data)

        
