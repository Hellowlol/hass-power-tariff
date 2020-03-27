"""Support for power tariff."""
import logging
import time
from operator import attrgetter

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.const import (EVENT_HOMEASSISTANT_START, SERVICE_TURN_OFF,
                                 SERVICE_TURN_ON)
from homeassistant.helpers import discovery
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
                vol.Optional("tariffs"): vol.All(
                    cv.ensure_list, [lambda value: TARIFF_SCHEMA(value)]
                ),
                vol.Optional("devices"): vol.All(cv.ensure_list, [DEVICE_SCHEMA]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up using yaml config file."""
    _LOGGER.info("Setup switch method!")

    config = config[DOMAIN]
    pc = PowerController(hass, config)
    devs = []
    tariffs = []
    for device in config.get("devices"):
        dev = (hass, device)
        devs.append(dev)

    for tariff in config.get("tariffs"):
        tar = Tariff(tariff)
        tariffs.append(tar)

    def cb(*args, **kwargs):
        # We don't really care about the cb, it just kick off everthing.
        pc.update()

    def ha_ready_cb(event):
        pc.ready = True
        # get_entity_object(hass, "switch.stor_kule")

    pc.add_tariff(tariffs)
    hass.data[DOMAIN] = pc

    hass.bus.listen(EVENT_HOMEASSISTANT_START, ha_ready_cb)
    track_state_change(hass, entity_ids=config.get("monitor_entity"), action=cb)

    hass.async_create_task(
        discovery.async_load_platform(
            hass, "switch", DOMAIN, config.get("devices"), config
        )
    )

    return True


class Tariff:
    def __init__(self, settings):
        self.name = settings.get("name")
        self.enabled = settings.get("enabled")
        self.priority = settings.get("priority")
        self.limit_kwh = settings.get("limit_kwh")
        self.over_limit_acceptance = settings.get("over_limit_acceptance")
        self.over_limit_acceptance_seconds = settings.get(
            "over_limit_acceptance_seconds"
        )
        self.restrictions = settings.get("restrictions", {})

    def valid(self):
        """validate if the tariff is valid (active)"""
        now = dt_util.now()

        if not len(self.restrictions):
            _LOGGER.debug("No restrictions are added, as result its always valid..")
            return True
        else:
            # Check for valid date range
            if (
                self.restrictions["date"]["start"] < now.date()
                and now.date() < self.restrictions["date"]["end"]
            ):
                if now.strftime("%a").lower() in self.restrictions["weekday"]:
                    if (
                        self.restrictions["time"]["start"] < now.time()
                        and now.time() < self.restrictions["time"]["end"]
                    ):
                        return True
                    else:
                        _LOGGER.debug(
                            "%s  is not in valid time range start %s end %s",
                            now.time(),
                            self.restrictions["time"]["start"],
                            self.restrictions["time"]["end"],
                        )

                else:
                    _LOGGER.debug(
                        "today %s is not in %s",
                        "".join(self.restrictions["weekday"]),
                        now.strftime("%a"),
                    )

            else:
                _LOGGER.debug(
                    "%s is not in valid date range start: %s end %s",
                    now.date(),
                    self.restrictions["date"]["start"],
                    self.restrictions["date"]["end"],
                )

        return False

    @property
    def tariff_limit(self):
        """ """
        return self.limit_kwh * (1 + self.over_limit_acceptance)


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

        # Remove me later
        import itertools
        t = [2000] * 6 + [3000] * 6 + [2500] * 6 + [1000] * 6
        self.t = itertools.cycle(t)
        # remove me later.

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
        """Check if we have a valid tariff we should use, sets the first valid tariff as the current"""
        for tariff in self.tariffs:
            if tariff.enabled and tariff.valid():
                _LOGGER.debug("Selected %s as current tariff", tariff.name)
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

    @property
    def current_power_usage_fake(self):
        """Just faked, just tired of turning on and off the stove.."""
        return int(next(self.t))

    def pick_minimal_power_reduction(self):
        """Turns off devices so we dont exceed the tariff limits."""
        _LOGGER.debug("Checking what devices we can turn off")
        power_reduced_kwh = 0
        devs = []

        current_power_usage = self.current_power_usage

        for device in sorted(self.devices, key=attrgetter("priority")):
            if device.is_on is False:
                _LOGGER.info("Device %r has been manually disabled", device)
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
                dev.proxy_turn_off()

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
            _LOGGER.debug(
                "current_power_usage: %s, limit %s",
                self.current_power_usage,
                self.current_tariff.tariff_limit,
            )
            return False

    def check_if_we_can_turn_on_devices(self):
        """Turn off any devices we can without exceeding the tariff"""
        # to turn on we dont allow temp usage to exceed tariff.
        _LOGGER.debug("Checking if we can turn on any devices")
        for device in self.devices:
            # Make sure we only turn on stuff that pc has turned off.
            if device.action == SERVICE_TURN_OFF and device.is_proxy_device_off():
                if (
                    # Dunno how helpfull it is to check the device current usage as
                    # if its turned off it should be very low.
                    self.current_power_usage + device.get_power_usage()
                    < self.current_tariff.tariff_limit
                ):
                    _LOGGER.debug(
                        "Device %s has been turned off by power controller, tring to turn it on",
                        device.turn_on_entity,
                    )
                    device.proxy_turn_on()
                else:
                    _LOGGER.debug(
                        "Cant turn on %s without exceeding tariff_limit",
                        device.turn_on_entity,
                    )
            else:
                _LOGGER.debug(
                    "%s is off or wasnt turned off by pc.", device.turn_on_entity
                )

    def update(self, power_usage=None):
        """Main method that really handles most of the work."""
        if self.ready is False:
            return

        self.check_tariff()

        if self.current_tariff.valid():
            reduce_power = self.should_reduce_power()
            _LOGGER.debug(
                "Should we reduce power: %s, current usage: %s",
                reduce_power,
                self.current_power_usage,
            )
            if reduce_power:
                self.pick_minimal_power_reduction()
            else:
                self.check_if_we_can_turn_on_devices()
