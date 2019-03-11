"""
GREE空调 遥控为型号YB0FB2的机型 BY 菲佣 1.0
"""
from datetime import timedelta
from base64 import b64encode, b64decode
import asyncio
import binascii
import logging
import socket

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, DOMAIN,
    ClimateDevice, PLATFORM_SCHEMA, STATE_AUTO,
    STATE_COOL, STATE_HEAT, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW,
    SUPPORT_OPERATION_MODE)
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE, ATTR_UNIT_OF_MEASUREMENT,
    CONF_NAME, CONF_HOST, CONF_MAC, CONF_TIMEOUT)
from homeassistant.helpers import condition
from homeassistant.helpers.event import (
    async_track_state_change, async_track_time_interval)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['sensor']

DEFAULT_TOLERANCE = 0.3
DEFAULT_NAME = 'GREE Thermostat'

DEFAULT_TIMEOUT = 10
DEFAULT_RETRY = 3

DEFAULT_MIN_TMEP = 16
DEFAULT_MAX_TMEP = 30
DEFAULT_STEP = 1

CONF_SENSOR = 'target_sensor'
CONF_TARGET_TEMP = 'target_temp'
devtype = 0x2712

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    vol.Required(CONF_SENSOR): cv.entity_id,
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float)
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the generic thermostat platform."""
    import broadlink
    ip_addr = config.get(CONF_HOST)
    mac_addr = binascii.unhexlify(
        config.get(CONF_MAC).encode().replace(b':', b''))

    name = config.get(CONF_NAME)
    sensor_entity_id = config.get(CONF_SENSOR)
    target_temp = config.get(CONF_TARGET_TEMP)

    broadlink_device = broadlink.rm((ip_addr, 80), mac_addr, devtype)
    broadlink_device.timeout = config.get(CONF_TIMEOUT)
    try:
        broadlink_device.auth()
    except socket.timeout:
        _LOGGER.error("Failed to connect to device")

    async_add_devices([DemoClimate(
            hass, name, target_temp, None, None, None, None, None,
            None, 'off', None, DEFAULT_MAX_TMEP, DEFAULT_MIN_TMEP, 
            broadlink_device, sensor_entity_id)])


class DemoClimate(ClimateDevice):
    """Representation of a demo climate device."""

    def __init__(self, hass, name, target_temperature, target_humidity,
                away, hold, current_fan_mode, current_humidity,
                current_swing_mode, current_operation, aux,
                target_temp_high, target_temp_low,
                broadlink_device, sensor_entity_id):
                 
        """Initialize the climate device."""
        self.hass = hass
        self._name = name if name else DEFAULT_NAME
        self._target_temperature = target_temperature
        self._target_humidity = target_humidity
        self._away = away
        self._hold = hold
        self._current_humidity = current_humidity
        self._current_fan_mode = current_fan_mode
        self._current_operation = current_operation
        self._aux = aux
        self._current_swing_mode = current_swing_mode
        self._fan_list = ['On Low', 'On High', 'Auto Low', 'Auto High', 'Off']
        self._operation_list = ['heat', 'cool', 'auto', 'off']
        self._swing_list = ['Auto', '1', '2', '3', 'Off']
        self._target_temperature_high = target_temp_high
        self._target_temperature_low = target_temp_low
        self._max_temp = target_temp_high + 1
        self._min_temp = target_temp_low - 1
        self._target_temp_step = DEFAULT_STEP

        self._unit_of_measurement = TEMP_CELSIUS
        self._current_temperature = None

        self._device = broadlink_device

        async_track_state_change(
            hass, sensor_entity_id, self._async_sensor_changed)
        
        sensor_state = hass.states.get(sensor_entity_id)
        if sensor_state:
            self._async_update_temp(sensor_state)

    @callback
    def _async_update_temp(self, state):
        """Update thermostat with latest state from sensor."""
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)

        try:
            self._current_temperature = self.hass.config.units.temperature(
                float(state.state), unit)
        except ValueError as ex:
            _LOGGER.error('Unable to update from sensor: %s', ex)

    @asyncio.coroutine
    def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle temperature changes."""
        if new_state is None:
            return

        self._async_update_temp(new_state)
        yield from self.async_update_ha_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._max_temp
    
    @property
    def target_temperature_step(self):
        return self._target_temp_step
    
    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature


    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._target_temperature_high

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._target_temperature_low

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def current_hold_mode(self):
        """Return hold mode setting."""
        return self._hold

    @property
    def is_aux_heat_on(self):
        """Return true if away mode is on."""
        return self._aux

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if kwargs.get(ATTR_TARGET_TEMP_HIGH) is not None and \
           kwargs.get(ATTR_TARGET_TEMP_LOW) is not None:
            self._target_temperature_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
            self._target_temperature_low = kwargs.get(ATTR_TARGET_TEMP_LOW)

        if self._target_temperature < self._target_temperature_low:
            self._current_operation = 'off'
            self._target_temperature = self._target_temperature_low
        elif self._target_temperature > self._target_temperature_high:
            self._current_operation = 'off'
            self._target_temperature = self._target_temperature_high
        elif self._current_temperature and (self._current_operation == "off" or self._current_operation == "idle"):
            self.set_operation_mode('auto')
            return
            
        self._sendpacket()
        self.schedule_update_ha_state()

    def set_humidity(self, humidity):
        """Set new target temperature."""
        self._target_humidity = humidity
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        self._current_swing_mode = swing_mode
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan):
        """Set new target temperature."""
        self._current_fan_mode = fan
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        self._current_operation = operation_mode
        self._sendpacket()
        self.schedule_update_ha_state()

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.schedule_update_ha_state()

    def set_hold_mode(self, hold):
        """Update hold mode on."""
        self._hold = hold
        self.schedule_update_ha_state()

    def turn_aux_heat_on(self):
        """Turn away auxillary heater on."""
        self._aux = True
        self.schedule_update_ha_state()

    def turn_aux_heat_off(self):
        """Turn auxillary heater off."""
        self._aux = False
        self.schedule_update_ha_state()
    
    def _auth(self, retry=2):
        try:
            auth = self._device.auth()
        except socket.timeout:
            auth = False
        if not auth and retry > 0:
            return self._auth(retry-1)
        return auth    

    def _sendpacket(self,retry=2):
        """Send packet to device."""
        cool = ("JgCSAAABJpMVNhUSFhIVNhUSFTYVEhYSFRIVEhYSFRIVEhYSFRIVEhYSFRIVEhUTFRIVNhUSFhIVEhUSFRIWEhU2FRIWNRYSFRIVNhUSFgACjRU2FTYVEhYSFRIVEhYSFRIVEhYSFRIVEhUTFTYVEhUSFhIVEhUSFRMVEhUSFRIWEhUSFRIWEhUSFTYVEhY2FRIVAA0FAAAAAAAA",
"JgCSAAABJpIVNhYSFRIVNhUSFjUWEhUSFTYVExUSFRIVEhYSFRIVEhYSFRIVEhYSFRIVNhUSFhIVEhUSFhIVEhU2FRIWNhUSFRIVNhUTFQACjRU2FTYVEhYSFRIVEhYSFRIVEhYSFRIVEhYSFTYVEhUSFhIVEhUSFhIVEhUSFRMVEhUSFRMVEhUSFRIWNhU2FRIVAA0FAAAAAAAA",
"JgCSAAABJpIWNhUSFRIVNhUSFjYVEhUSFhIVNhUSFRIWEhUSFRIVExUSFRIVExUSFRIVNhUTFRIVEhUSFhIVEhU2FRMVNhUSFRIWNRYSFQACjRU2FTYWEhUSFRIWEhUSFRIVExUSFRIVEhcRFTYVEhUTFRIVEhUTFRIVEhUSFhIVEhUSFhIVEhUSFjUWNhU2FRIVAA0FAAAAAAAA",
"JgCSAAABJpIVNhUTFRIVNhUSFjUWEhUSFTYVNhYSFRIVEhUTFRIVEhUSFhIVEhUSFhIVNhUSFRIWEhUSFRIWEhU2FRIVNhYSFRIVNhUSFgACjRU2FTYVEhYSFRIVEhUTFRIVEhUSFhIVEhUSFjYVEhUSFRIWEhUSFRIWEhUSFRIWEhUSFRIWEhUSFRIVExUSFTYVAA0FAAAAAAAA",
"JgCSAAABJpIVNhYSFRIVNBcSFjYVEhUSFRIWEhU2FRIVExUSFRIVEhYSFRIVEhYSFRIVNhUSFhIVEhUSFhIVEhU2FRIWNhUSFRIVNhYSFQACjRU2FTYWEhUSFRIVExUSFRIVEhYSFRIVEhYSFTYVEhUTFRIVEhUSFhIVEhUSFhIVEhUSFhIVEhUSFTYWEhUSFTYVAA0FAAAAAAAA",
"JgCSAAABJpEWNhUSFhIVNhUSFTYWEhUSFTYVEhY2FRIVEhUSFhIVEhUSFhIVEhUSFhIVNhUSFRIWEhUSFRIWEhU2FRIVNhUTFRIVNhUSFgACjRU2FTYVEhUTFRIVEhUSFhIVEhUSFhIVEhUSFjYVEhUSFRIWEhUSFRIWEhUSFRIWEhUSFRIVExUSFRIVNhYSFTYVAA0FAAAAAAAA",
"JgCSAAABJZMVNhUSFhIVNhUSFTYWEhUSFRIVNhY1FhIVEhUSFhIVEhUSFhIVEhUSFhIVNhUSFRIWEhUSFRIWEhU2FRIVNhUSFhIVNhUSFQACjhU2FTYVEhUSFhIVEhUSFhIVEhUSFhIVEhUSFjUWEhUSFRIWEhUSFRIWEhUSFRIVExUSFRIVEhYSFTYVNhUSFjUWAA0FAAAAAAAA",
"JgCSAAABJZMVNhUSFhIVNhUSFTYWEhUSFTYVNhU2FhIVEhUSFRMVEhUSFRIWEhUSFRIWNhUSFRIVEhYSFRIVEhY2FRIVNhUSFhIVNhUSFQACjRY2FTYVEhUSFhIVEhUSFRMVEhUSFRMVEhUSFTYVExUSFRIVExUSFRIVEhYSFRIVEhYSFRIVEhYSFRIVEhU2FjYVAA0FAAAAAAAA",
"JgCSAAABJpMVNhUSFRIWNhUSFTYVEhYSFRIVEhYSFTYVEhUSFhIVEhUSFRMVEhUSFRIWNhUSFRIVExUSFRIVEhY2FRIVNhUSFhIVNhUSFQACjRY2FTYVEhUSFhIVEhUSFhIVEhUSFhIVEhUSFTYWEhUSFRIVExUSFRIVEhYSFRIVEhYSFRIVEhYSFTYVEhU2FTYWAA0FAAAAAAAA",
"JgCSAAABJpIVNhYSFRIVNhUSFjUWEhUSFTYVEhYSFTYVEhYSFRIVEhUSFhIVEhUSFhIVNhUSFRMVEhUSFRIWEhU2FRIVNhYSFRIVNhUSFgACjRU2FTYVEhYSFRIVEhYSFRIVEhUTFRIVEhUSFjYVEhUSFRMVEhUSFRIWEhUSFRIWEhUSFRIWEhUSFRIWNRY2FTYVAA0FAAAAAAAA",
"JgCSAAABJpIWNRYSFRIVNhUSFjYVEhUSFRMVNhUSFTYVEhYSFRIVEhYSFRIVEhUTFRIVNhUSFhIVEhUSFhIVEhU2FRIWNRYSFRIVNhUTFQACjRU2FTYVEhYSFRIVEhYSFRIVEhYSFRIVEhYSFTYVEhUSFhIVEhUSFhIVEhUSFRMVEhUSFRIWEhUSFTYVNhY1FjYVAA0FAAAAAAAA",
"JgCSAAABJZMVNxQTFBMVNhUTFDcUExQTFTYVNxQTFDcUExUTFBMUExUTFBMUExUTFBMUNxQTFRMUExQTFRMUExQ3FBMVNhUTFBMUNxQUFAACjhQ3FDcUExUTFBMUExUTFBMUExUTFBMUExUTFDcUExQTFRMUExQTFRMUExQTFBQUExQTFBMVExQTFBMVExQTFBMVAA0FAAAAAAAA",
"JgCSAAABJZMUNxUTFBMUNxQTFTYVExQTFBMVExQ3FDcUExUTFBMUExUTFBMUExQUFBMUNxQTFRMUExQTFBMVExQ3FBMVNhUTFBMUNxQTFQACjhQ3FDcUExUTFBMUExUTFBMUExQUFBMUExQTFTcUExQTFBMVExQTFBMVExQTFBMVExQTFBMVExQTFDcUExUTFBMUAA0FAAAAAAAA",
"JgCSAAABJpIUNxUTFBMUNxQTFTYVExQTFDcUExU3FDcUExQTFRMUExQTFRMWERQTFBMWNhQTFBMWEhYRFhEWERc1FBMWNRQTFRMWNRYRFgACjRQ3FDcWERYRFhIWERQTFhIWERYRFhIWERYRFjUWEhYRFhEWEhYRFhEWERcRFhEWERYSFhEWEhUSFhEWNRYRFhIWAA0FAAAAAAAA",
"JgCSAAABJZMUNxUTFBMUNxQTFTYVExQTFBMVNxQ3FDcUExQTFRMUExQTFRMUExQTFRMUNxQTFBQUExQTFBMVExQ3FBMUNxQTFRMUNxQTFAACjhU3FDcUExQTFRMUExQTFRMUExQTFRMUExQTFTYVExQTFBMVExQTFBMUExUTFBMUExUTFBMUExUTFDcUNxQTFRMUAA0FAAAAAAAA")
        off = "JgCSAAABJZMVNhUSFRMVEhU2FTYVEhYSFRIVEhYSFTYVEhUSFhIVEhUSFhIVEhUSFRMVNhUSFRIVExUSFRIVEhY2FRIVNhUSFhIVNhUSFQACjRYSFRIVEhYSFRIVEhUTFRIVNhUSFhIVEhUSFTYWEhUSFRIWEhUSFRIVEhYSFRIVEhYSFRIVEhYSFTYVEhU2FRMVAA0FAAAAAAAA"
        heat = ("JgCSAAABJpMVEhUSFjUWNhUSFRIVExUSFRIVEhYSFRIVEhYSFRIVEhYSFRIVEhUTFRIVNhUSFhIVEhUSFRMVEhU2FRIWNRYSFRIVNhUSFgACjRUSFRIWEhYRFRIWEhUSFRIWEhUSFRIVExUSFTYVEhYSFRIVEhUTFRIVEhUSFhIVEhUSFhIVEhUSFhIVEhYRFjUWAA0FAAAAAAAA",
"JgCSAAABJpIVEhYSFTYVNhUSFhIVEhUSFjUWEhUSFRIWEhUSFRIWEhUSFRIVExUSFRIVNhYSFRIVEhUTFRIVEhU2FRMVNhUSFRIWNRYSFQACjRUSFhIVEhUSFhIVEhUSFhIVEhUSFRMVEhUSFTYWEhUSFRIVExUSFRIVEhYSFRIVEhYSFRIVEhYSFTYVEhUSFjYVAA0FAAAAAAAA",
"JgCSAAABJZMVEhUTFTYVNhUSFRIWEhUSFRIWNRYSFRIVEhYSFRIVEhYSFRIVEhYSFRIVNhUSFhIVEhUSFhIVEhU2FRIWNRYSFRIVNhUSFgACjRUSFRIWEhUSFRIWEhUSFRIWEhUSFRIWEhUSFTYVEhYSFRIVEhYSFRIVEhUTFRIVEhUSFhIVEhUSFhIVNhUSFTYWAA0FAAAAAAAA",
"JgCSAAABJpIVEhYSFTYVNhUSFRMVEhUSFTYWNRYSFRIVEhYSFRIVEhYSFRIVEhUTFhEVNhUSFhIVEhUSFRMVEhU2FRIWNRYSFRIVNhUSFgACjRUSFRIWEhUSFRIWEhUSFRIWEhUSFRIWEhUSFTYVEhYSFRIVEhYSFRIVEhUTFRIVEhUSFhIVEhUSFjUWNhUSFTQXAA0FAAAAAAAA",
"JgCSAAABJpIWEhUSFTYVNhUSFhIVEhUSFhIVEhU2FRIWEhUSFRIWEhUSFRIWEhUSFRIWNRYSFRIVEhYSFRIVEhY1FhIVNhUSFRIWNhUSFQACjRUTFRIVEhUSFhIVEhUSFhIVEhUSFhIVEhUSFjUWEhUSFRIWEhUSFRIWEhUSFRIVExUSFRIVEhYSFRIVEhY1FjYVAA0FAAAAAAAA",
"JgCSAAABJpIVExUSFTYVNhUSFhIVEhUSFjUWEhU2FRIVExUSFRIVEhYSFRIVEhYSFRIVNhUSFhIVEhUSFhIVEhU2FRIWNhUSFRIVNhYSFQACjRUSFhIVEhUSFRMVEhUSFRIWEhUSFRIWEhUSFTYVEhYSFRIVEhYSFRIVEhYSFRIVEhYSFRIVEhUSFjYVEhU2FTYVAA0FAAAAAAAA",
"JgCSAAABJ5EXERcQFzQXNBcRFhEXNBcRFhEWNRc0FxAXERYRFxAXERYRFxAXERYRFhEXNBcRFhEWERcRFhEWERc0FxEWNRYRFxAXNBcRFgACjBcQFxEWERYRFzQXERYRFxAXERYRFhEXERYRFjUWERcRFhEWERcRFhEWERcRFhEWERcRFhEWERcQFzUWNRY1FjUWAA0FAAAAAAAA",
"JgCSAAABJ5IWERYRFzQXNRYRFhEXERYRFjUWNRY1FxEWERYRFxAXERYRFxAXERYRFhEXNBcRFhEXEBcRFhEWERc0FxEWNRYRFxEWNRYRFgACjBcRFhEWERcRFhEWERcRFhEWERcQFxEWERYRFzQXERYRFxAXERYRFhEXERYRFhEXERYRFhEXERYRFjUWNRc0FzQXAA0FAAAAAAAA",
"JgCSAAABJpMVEhUSFjUWNhUSFRIVEhYSFRIVEhYSFjUVEhUSFhIVEhUSFhIVEhUSFhIVNhUSFRIWEhUSFRIWEhU2FRIVNhUTFRIVNhUSFQACjhUSFRIWEhUSFRIVExUSFRIVEhYSFRIVEhYSFTYVEhUSFhIVEhUSFhIVEhUSFhIVEhUSFRMVEhUSFRIWEhUSFRIWAA0FAAAAAAAA",
"JgCSAAABJ5EXERYRFzQXNBcRFhEWERcRFhEWERcRFjUWERYRFxEWERYRFxEWERYRFxEWNRYRFhEXERYRFhEXERY1FhEWNRYRFxEWNRYRFwACixcRFhEXEBcRFhEWERcRFhEWERcRFhEWERcRFjUWERYRFxEWERYRFxEWERYRFxAXERYRFhEXERYRFhEXERYRFhEXAA0FAAAAAAAA",
"JgCSAAABKJAXERcQFzQXNBcRFhEXEBcRFhEXNBcQFzQXERcQFxAXERYRFxAXERYRFxAXNBcRFhEXEBcRFhEXEBc0FxEWNRcQFxEWNRYRFwACixcRFhEXEBcRFhEXEBcRFhEWERcQFxEWERcQFzQXERYRFxAXERYRFxAXERYRFxAXERYRFxAXERYRFxAXNBcRFhEXAA0FAAAAAAAA",
"JgCSAAABJpIVEhYSFTYVNhUSFRIWEhUSFTYVNhYSFTYWERUSFhIVEhUSFhIVEhUSFhIVNhUSFRIWEhUSFRIWEhU2FRIVNhUSFhIVNhUSFQACjhUSFRIVExUSFRIVEhYSFRIVEhYSFRIVEhYSFTYVEhUSFhIVEhUSFhIVEhUSFRMVEhUSFRMVEhUSFTYVNhYSFRIVAA0FAAAAAAAA",
"JgCSAAABJpIVEhYSFTYVNhUSFhIVEhUSFhIVEhU2FTYVEhYSFRIVEhcRFRIVEhYSFRIVNhUSFhIVEhUSFhIVEhU2FRIWNhUSFRIVNhYSFQACjRUSFhIVEhUSFRIWEhUSFRIWEhUSFRIXERUSFjUVEhYSFRIVEhYSFRIVEhYSFRIVEhUTFRIVEhUSFhIVEhU2FRMVAA0FAAAAAAAA",
"JgCSAAABJpIWEhUSFTYVNhYSFRIVEhYSFTYVEhU2FTYWEhUSFRIVExUSFRIVExUSFRIVNhUTFRIWERUSFhIVEhU2FRMVNhUSFRIWNRYSFQACjRUSFhIVEhUSFhIVEhUSFhIVEhUSFRMVEhUSFTYWEhUSFRIVExUSFRIVEhYSFRIVEhcRFRIVEhYSFTYVEhU2FRMVAA0FAAAAAAAA",
"JgCSAAABJ5IVEhYRFzQXNBcRFRIWERYSFRIVNhU2FTYWEhUSFRIXERUSFRIXERUSFhEVNhUTFhEWERcQFhIWERY1FRMVNhUSFRIWNRYSFgACjBUSFhIWERUSFxEVEhYRFhIVEhYRFRMVEhUSFzQWEhUSFhEVExUSFRIXEBcRFhEWERYSFRIVEhYSFRIWNRU2FhEXAA0FAAAAAAAA")
        
        if (self._current_operation == 'idle') or (self._current_operation =='off'):
            sendir = b64decode(off)
        elif self._current_operation == 'heat':
            sendir = b64decode(heat[int(self._target_temperature) - self._target_temperature_low])
        elif self._current_operation == 'cool':
            sendir = b64decode(cool[int(self._target_temperature) - self._target_temperature_low])
        else:
            if self._current_temperature and (self._current_temperature < self._target_temperature_low):
                sendir = b64decode(heat[int(self._target_temperature) - self._target_temperature_low])
            else:
                sendir = b64decode(cool[int(self._target_temperature) - self._target_temperature_low])
        
        try:
            self._device.send_data(sendir)
        except (socket.timeout, ValueError) as error:
            if retry < 1:
                _LOGGER.error(error)
                return False
            if not self._auth():
                return False
            return self._sendpacket(retry-1)
        return True