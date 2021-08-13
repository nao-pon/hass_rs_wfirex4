"""RS-WFIREX4 Load Platform integration."""

from getmac import get_mac_address

import logging
import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers import discovery
from homeassistant.helpers.device_registry import format_mac
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL, CONF_MAC

DOMAIN = 'rs_wfirex4'
DEFAULT_NAME = 'RS-WFIREX4'
DEFAULT_SCAN_INTERVAL = 60
PLATFORMS = ['remote', 'sensor']
CONF_TEMP_OFFSET = 'temp_offset'
CONF_HUMI_OFFSET = 'humi_offset'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema([
        vol.Schema({
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_MAC, default=''): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.positive_int,
            vol.Optional(CONF_TEMP_OFFSET, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=-10, max=10)),
            vol.Optional(CONF_HUMI_OFFSET, default=0.0): vol.All(vol.Coerce(float), vol.Range(min=-20, max=20)),
        }),
    ])
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, configs):
    for config in configs.get(DOMAIN):
        if (config.get(CONF_MAC) == ''):
            ip = config.get(CONF_HOST)
            mac = get_mac_address(ip)
            _LOGGER.info("Detected Mac address as %s.", mac)
            if mac is None or mac == "00:00:00:00:00:00":
                ips = ip.split('.')
                mac = "00:1C:C2:" + format(int(ips[1]), '02X') + ":" + format(int(ips[2]), '02X') + ":" + format(int(ips[3]), '02X')
                _LOGGER.warning("The MAC address could not be detected automatically. Use \"%s\" as the fake address. You can specify the correct MAC address with the \"mac\" option for more perfect operation.", mac)

            config['uid'] = format_mac(mac)
        else:
            config['uid'] = format_mac(config.get(CONF_MAC))
        for component in PLATFORMS:
            await hass.helpers.discovery.async_load_platform(component, DOMAIN, config, configs)

    return True
