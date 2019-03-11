"""
Zhigao空调 BY 菲佣 1.0
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
DEFAULT_NAME = 'Zhigao Thermostat'

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
        if sensor_state != 'unknown' and sensor_state:
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
        cool = ("JgDIAMbxFTQVNBU0FTQUNRI3EjcSNxISEhISEhISFBAVDxUPExESNxI3FDUSNxQ1FTQVNBU0FQ8UEBUPFQ8VDxUPFBASEhISEhISNxI3EjUUNxM2FTQVMxY0FQ8VDxUPEhISEhISEjcSEhQQFTQVNBU0FTQTNhISEjcSNxISEhMVDxUPFQ8TNhE4EjcSNxI3EhISNxQ1FQ8VDxUPFQ8TERM2EhISEhISEjcSEhI3ExEVNBUPFQ8VNBUPFTQUEBUzExISNxI3EvMSAA0F",
"JgDIAMXzEjcSNxM2FDUVNBI3EjcVNBISERMRExISEhISEhMRFQ8UNRU0FDUUNRM1EzcROBE4EhISEhISEhIUEBUPFBAUEBQ1EhISNxE4ETgSNxI3EjcSEhQ1FBAVDxUPFBAVDxQQEzYSEhISETgSNxI3EjcTNhQQFDUVNBUPFBATERISERMRExI3EjcSNxI3FBAUNRQ1FDUVDxUPExESEhE4ERMSEhISEjcSEhQ1FRAUNRUPFQ8UNRISEjcRExI3EhISNxI3FvAUAA0F",
"JgDIAMfxFzQUNRU0FDUTNhI2EjcSOBESEhMVDxMREhESEhITFQ8UNRM2EjYSOBM2FDUTNxI3EhMRExISFBAUEBMTERMSEhQ1FBAUNRU0FDUUNRM1EzYTEhI4ERMTERQQFBAUEBUPFzQUEBMREjcSNhI3EjcSNxITEjcTNhQQFBAUEBUPERITNxMRFDUUNRU0FQ8UNRQ1EhIRNxISEhISEhI4EhIUEBQQFDUVDxQ1FBASNhISEhMSNxQQFDUUEBQ1FBAUNRM2EvISAA0F",
"JgDIAMjwFDUTNhI3ETgSNxI3EjcSNxISFBAVDxUPFRAREhUPFQ8UNRU0FTQUNRM2EjcSNxI3EhISEhMRFBAVDxQQFBAVDxM2EhISNxI3EjcSNxI3EjcUEBQ1FRATEBQQFQ8VDxUQEjcSEhISFDUVNBU0FTQVNBQQEzYSNxETEhISEhISEhIVDxUPFDUVNBU0ExESNxE4EjcSNxISEhITERQ1FQ8VDxUPFTQUEBI3EhIVNBUPFQ8VNBMREjcRExI3EhISNxI3EvMUAA0F",
"JgDIAMTzEjcSNxQ1FTQVNBU1FDUUNRMREhISEhESEhISEhISEhIbNxI3EjcSNxI3EjcVNBU0FRAUEBQQFBASEhIREhISEhI3EhETNxQ1FTQVNBU1FDUUEBM2EhIREhISEhISFBMREjcSERISEjcSNxY0FTQVNRQQEzYRNxISEhISEhUPFQ8VNhU1FBAUNRI2EhISNxI3EhISEhI3FQ8VERQ0FRAUEBQREjYSEhE3EhISNxYOFQ8VNBUQFDUUEBI3EhIRNxI3EvMSAA0F",
"JgDIAMT0EjcUNRI3EjcVNBQ1FTQVNBUPFBATERISERMRExISEhISNxQ1FTQVNBQ1FTQUNRM2EhIRExETERMSEhISFBATERI3ERMSNxE4ETgSNxI3EjcUEBQ1FBAUEBUPFRASEhISETgRExISEjcVNRU0FDUVNBUPEjcSNxISEhIUEBQQFBAWEBI3ERMROBI3EhIWNBM2EjcRExE4EhIRExE4EhISEhISFTQUEhI3EhITNhQQFQ8VNBUPFTQUEBI2ExIROBE4EvMSAA0F",
"JgDIAMjwFTUUNRQ1EjYTNhI3EjcSNhMSEhIVDxUQFBAUEBQQFBATNhI2EjcSNxI3EjcSNxU0FRAUEBQQFBAUEBMQExIREhI3EhISNxI3EjcVNBU1FDQVEBQ1FBATERESEhISEhISEjcSEhUQFDQVNRQ1FDUUNRMREjYTNhISEhISEhISEhMSNhISEhISNxI3EhIVNBU0FRAUMxY1ExETEBM2EhISEhISEjcSEhM2FQ8VNRQQFBAUNRQQFDUUEBQ1EhISNhI3EvMSAA0F",
"JgDIAMjwFDUTNhI3ETgSNxI3EjcSNxISFQ8VDxUPFQ8UEBUPFBAVNBQ1EzYSNxI3EjcSNxI3EhITERUPFRAREhUPFQ8VDxI3EhISORQ1EzYSNxI3EjcSEhI3EhITERUPFQ8VERETEjcSEhISEjcSOBU0FTIXNBQQFTQSNxISEhISEhISEhISEhMRFBAVNBU0FQ8UNRM2EjcSNxI3EhISEhI3ExEUEBUPFDUUEBQ1ExESNxISFBASNxISEjcSEhI3EhITNhQ1FfAUAA0F",
"JgDIAMXzEjcSNxI3EjcVNBU0FTQVNBUPFRARExETERISEhISEhISNxM2FTQVNBU0FTQVNBQ2ERISEhITERMREhISEhISEhI3EhIUNRU0FTQVNBU0FTQUERE3EhISEhISEhISEhISFTQVDxUPFTQVNBQ2ETgRNxISEjcSNxISEhIVDxUPFQ8VNBU0FTQVEBQ0FQ8VNRE2ExISEhISEjcVDxU0FQ8VDxUPFTURExE3EhISNxISEhISNxMRFTQVDxU0FQ8VNBQ2EfQRAA0F",
"JgDIAMbzEjcUNRQ1FDUVNBU0EzYSNxIREhISEhITERMSEhISERISNxI3EjgSNxM2FDUUNRQ1FBASEhISERISEhITERMSEhI3Fg8UNRU0FTQUNRI2EjgSEhM2FBAUEBMSERISEhISEjcSEhMSFDUUNRQ1ETcSNxcQFDUUNRQQEhIRExESFxAUEBI2EjcSEhI3ExISOBI3EzYUEBQQFTUUEBM2EhIREhISEjcSExI3ExEUNRQQFBAXNBQQEzUSEhI3EhIXNBQ1FfAUAA0F",
"JgDIAMb0ETcSNxI3EjcSNxI3FDUVNBUPFQ8VDxQQEhISEhISEhISNxI3EjcVNBU0FTQVNBU0FBASEhISEhISEhISEhISEhU0FQ8VNBU0FTQVNBM2EjcSEhI3EhISEhISEhIUEBUPFTQVDxUQFTQVNBI3EjcSNxISEjcSNxISFBAVEBESEhIVNBUPFTQVDxU0FBATNBc0FQ8VNxESEjcSEhI3EhIVDxUREzYSEhI3EhISNxITFQ8VNBQQFTMWDxQ1ExISNxI3EvMSAA0F",
"JgDIAMTzEjcSNxI3EjcUNRU0FTQVNRQQFBATERISERISEhISEhISNxI3FTQVNBU0FTUUNRQ1ExESEhESEhISEhISExIREhI3EhISNxI3EjcVNBU0FTQVEBQ1FBAUEBIREhISEhISEjcSEhQQFTQVNBU0FTQVNBQREzYSNhISFQ8VEBQQFBAUEBISETcSEhI3EhISNxI3FTQVNBUPFTQVEBQ1ExESERISEjcSEhI3EhISNxUPFQ8VNBUQFDUTERI3EhESNxI3EvQRAA0F",
"JgDIAMbzEjcSOBI3FDUUNRQ1FDUVMhYQExESEhETERISExETEhITNhQ1FTQUNRQ1FDUTNhI2EhISExESEhMSEhMRFBAUEBQ1FBAUNRM2EjYSNxI3EjQVExI3EhIUEBQQFBAUEBQQEzYSEhISETcSOBE4EjcSNxQQFDUUNRUPFBATERIREhMRNxI3EhMSEhE4EhITNhQ1FBEUDxU0FDUTERI2ExESEhITETgRExI3FBAUNRUPFBAUNRQREjYUEBQ1FBAVNBQ1FPESAA0F",
"JgDIAMXzEjcUNRQ1FTQUNRQ1FDQTNxISERMRExISEhISEhQQFBAUNRU0FDUTNhI3ETgROBM2EhIRExETEhISEhISFBAUEBI3EhIROBE4EjcUNRQ1FDUUEBU0FQ8UERIREhIRExETETYUEhISEzYUNRQ1FTQVNBUPFTQTNhISERMRExQQFBAUEBM2ExESEhE4ERMROBI3EjgSEhI3FDUUEBQzFw8VDxMREjcSEhE4ExISNxISEhIUNRQQFDUVDxQ1FBETNRU0FPMRAA0F",
"JgDIAMjxFDUUNRM2EjYSNxI3EjcSNxISFBAVDxUQFBAUEBQQEhISNhI3EjcSNxI3EjcSNxU0FQ8VEBQQExETERISEhESEhI3EhISNxI3FTQVNBU0FTQVDxU0FRASEhIREhISEhISEjcSEhQQFTQVNBU1FDUUNRISEjYSNxISEhISEhISFBAVNBUQFBAUEBQ1ExESNxI2EhISNxI3EjcSEhU0FQ8VEBUQFDUTERI3ERISNxMRFQ8VNBUQFDUUEBQ1EhISNhI3EvMSAA0F")
        off = "JgDIAMXzEjcUNRU0FDUVNBU0FTQTORQPFBAUEBUPEhISEhQQFBAVNBU0EzYTNhI3EjcROBI3EhAUEhISFBAUEBQQFBAVDxU0ETgSNxI3EjcSNxQ1FDUVDxQQEhISEhISEhIUEBQQFTQUNRUPEzYSNxI3ETgROBISEhISNxISFBAUEBQQFQ8VDxM2EjcSEhE4ETcTNxI3EjcSEhQQFDUVDxQQFBASEhISETgRExI3EhISNxQQFQ8UNRQQFTQUEBM2ExESNxE4EvMSAA0F"
        heat = ("JgDIAMfxFDUUNRQ1FDUUNRM2EjYSNxISEhITEhISFBAUEBQQFw8UNRQ0FDYSNxM2FDUUNRQ1FBAUEBQQFBAUEBUPERISEhMSEhIUNRQ1FDQVNRQ1FDUTNhI3ERISEhISEhISEhMSFDUUEBQQFDUSNhI3EjcSNxISFjQTNhMSExAUEBQQFQ8TNhM2EjcSNhI3EjcSNhMSExISEhQQFBAUEBQQFBAUNRISETcSEhI3EhISOBISExEUNBUQFDUUEBQ1ExESNhI3EvMSAA0F",
"JgDIAMfyFDUSNxI2EjcSNxI3EjcUNRUPFQ8VEBQQFBATERMREhESNxI3EjcWMxU1FDUUNBQ2EhISERISEhISEhISEhIVDxU0FRAUNRQ1FDUSNhM2EjcSEhI3EhIUEhISEhISEhISFTQVEBQPFTYVNRQ1FDUSNhMREjcSNxISEhISEhcPFBAUEBQ1EzQUNxM2FDUVMRgPFTQTERUPFQ8VDxUQERISNxISEjcSEhU0FQ8VNRQQFBATNhIREjcSEhI3EhISNxQ1FfAVAA0F",
"JgDIAMfxFDUTNhI2EjcSNxI3EjcSNxMRFRAUEBQQFBAUEBQQExESNhI3EjcSNxI3EjcUNRU0FRAUEBQQFBATERISEhESEhI3EhISNxM2FTQVNRQ1FDUUEBM2EhISERISEhISEhISEzYVDxUPFTUUNRQ1FDUUNRISEjYSNxISFBAVEBQQFBAUNRQQFDcTNhI3EjYSNxISEhISNxISFBEUEBQQFBAUNRQQEzYSERI3EhITNhUPFRAUNBUQFDUUEBM2EhIRNxI3EvMSAA0F",
"JgDIAMTzEjcSNxU0FTQVNBU1FDUTNRMREhISEhISEhISEhQREhISNxE3EjcSNxU0FTQVNBU0FRATERISERISEhISEhISEhI3FBIRNxQ1FTQVNBU0FTQVEBI2ExESEhIUFBAUEBQQEjYSEhISEjkVNBU0FTUUNRISETcSNxISFQ8VDxUPFRIUEBISETcSNxI3EjcSNxISFTQVNBUQFA8VDxUQFBATNRISEjoREhI3EhISNxISFBAVNBUPFTQSEhI3EhISNxQ1FfAVAA0F",
"JgDIAMT0EjcSNxI3EjcUNRQ1FTQVNBUPFBATERISERMSEhISFQ8VNBQ2FDQVNBI3EjcSNxI1FRESEhISEhISEhQQFBEUEBU0FQ8VNBU0EzYTNhI3ETgSEhI3EhISEhISFBAUEBUPFTcTEBQQFDUVNBU0FDUTNhISETgSNhMTFQ8UEBQQExEVNBQ1FREROBI3EjcSNxISFBAVDxU0FQ8TERMRERMROBISEjcSEhI3FBAVNBQQFQ8VNBQQEzYSEhE4EhISNxI3EvMUAA0F",
"JgDIAMTzEjcSNxI3EzYVNBU1FDUVMhYQFBATERISERISEhISEhISNxM2FDYUNBU0FTUUNRQ1ExESEhETERISEhISEhIUERQ0FRAUNRQ1FDUUNRM2EjYSEhI3EhISEhMRFRAUEBQQFDUTEBUQFDUUNRQ1FDUTNhISETcSNxISEhITERQRFBAUEBQ1FBAUNRQ1EzYSNhISEjcSEhI3FBEUEBQQExETNhISFDUUEBQ1FBATNhITExAVNRQQFDUUEBQ2ERISNxI3EvMUAA0F",
"JgDIAMjwFTQVNRU0FDUSNxE4EjcSNxISEhITERUPFQ8UEhMQFQ8VNBU0FTQVNBI3EjcROBI3FQ8VDxQQExEVDxUPFQ8VDxQ1EhIROBE4EjcSNxI3EjcVDxU0FQ8VDxUPExETERETETgSEhUPFDUVNBU0FTQUNhQPFTQVNBUPFQ8TERISERMSNxISEhISNxI3EjcUNRUPFQ8VNBU0FBATERISERMROBISEjcSEhI3FBAVNBUPFQ8VNBUPFTQTERU0FQ8VNBI3EvMSAA0F",
"JgDIAMfwFTQVNRQ1FTQVNBU1FDUTNBQSERISEhISEhISEhQQFQ8VNhU1FDMWNRQ1EzYSNhI3EhISEhYPFBAUEBQQEhIUEBQ1FBAUNRM2EjYSNxI3EjcSEhI3EhIVDxUPFRAUEBQQFDUTERIREjcSNxI3EjYTNxQQFTQVNBUQFBAUDxUQFBAUEBQQEhISNhI3EjcSNxISFDUVNBU0FQ8VEBQQFBAUNRISEjYSEhI3EhISNxISFQ8VNBUQFDUUEBQ1ExESNhI3EvMSAA0F",
"JgDIAMfwFTQVNBU0FTQUNRI3EjcSNxISEhISEhUPFQ8VDxUPFQ8UNRM2EjYTNxI3EjcSNxI3FBAVDxUPFQ8VDxUPExESExE3EhISNxI3EjcUNRU1EjcSEhI3EhISEhMRFREVDxMREjcSEhISEjcSNxI3FTQVNBUPFTQVNBUPFBASEhISEhISNxI3EjcVDxU0FTQVNBUPFBATERISEjcSEhISEhISNxISEjcSEhI3EhISNxUPFQ8VNBUQFDQVDxQ1ExESNxI3EvUSAA0F",
"JgDIAMjwFTQUNRM2EjcROBI3EjcSNxISFQ8VDxUPFQ8VDxUPExESNxE4EjcSNxI3EzYVNBI3EhISEhISEhISEhISFQ8VDxM2FBATNhE4ETgSNxI3EzgSEhI3EhITERUPFQ8WEBUPFTQVDxMREjcROBE4EjMWNxISEzYVNBQQFQ8VDxUPFQ8TERI3ETgRExI3EjcSNxISFTQVDxUPFTQVDxQQFBASNxETETgSEhI3EhITNhUQERITNhUPFTQVDxU0FQ8VNBM2E/ITAA0F",
"JgDIAMTzEjcSNxI3FTMWNBU0FTUUNBUQExESEhESEhISEhISEhISNxQ3ETcSNxI3EjcSNxU0FQ8VDxUPFRAVDxUPFRAUEBQ1EhIRNxY2EjYSNxI3EjcSEhI3FQ8VDxUPFRAUEBQREjYSEhISEjcSNxczFTUUNRQQEjcVMxUPFRAUEBMREhIRNxcPFTQVDxU0FTUUNRMRERISNxISEjcSEhQSEhISNxISEjcVDxU0FQ8VMBkQFBASNxIREjkSEhI3EhISNxI3FfAVAA0F",
"JgDIAMT0EjMWNxI3EjcTNhU0FDUVNBUPFBATERISERMSEhIUEhIROBI3EjcSNxE4ETgSNxI3EhIVDxIREhMRExUPFQ8TERM2EhIROBI3EjcSNxI3FDUVDxU0FQ8VDxQQEhIRExETEjcSEhISEjcSNxI3FTQVNBUQEzUVNBMRERMSEhISEhISEhQQFTQVDxU0FTQVNBUPFTQVNBUPFDUSEhETEhISNxISEjcTERU0FBAVNBUPFQ8TNhISETgRExI3EhISNxI3FfAVAA0F",
"JgDIAMTzFTUSNhI3EjcSNxI3EjcUNRUPFRAUEBQQFBAUEBQQExERNxI3EjcSNxI3EzYVNBU1FBAUEBQQFBATERESFg8UEBQ1FBAUNRM2EjYSNxI3EjcSEhI3FQ8VEBQQFBAUEBQQEzYSERISEjcSNxI3EjcVNBUQFDQVNRQQEhESEhISEhIVNBU0FRAUEBQ1FDUUNRMREhESEhI3EjcSEhISExEVNBUQFDUUEBQ1FBATNRMRExEUNRUPFTQVEBQ1ExESNxI3EvMSAA0F",
"JgDGABU0FTQTORQ0FTQUNRM2EjcSEhISEhISEhISFQ8VDxUPFTQVNBQ1EzYSNxI3EjcSNxISEhIUEBUPFQ8VDxUPFQ8UNRMREjcSNxI3EjcSNxI3FBAVNBUPFBAVDxUPFBASEhE4EhISEhI3EjcSNxU0FTQVDxU0FTQVDxMRExESEhISEhISNxISEhIVNBU0FTQVEBQ0FQ8VNBQ1EhIRExISEjcSEhU0FQ8TNxQPFTQVDxUPFTQVDxM2EhIROBISEjcSNxLzEgANBQAA",
"JgDIAMTzFTQVNBU1FDQVNRQ1EzYSNhISEhISEhISEhIUEBUPFRAUNRI2EjcSNxI3EjcTNhU0FRAUEBQQFBAUEBQQEhISERI3EhISNxI3EjcSNxU0FTQWEBQ0FRATERMRERISEhISFTYSEhISFTQVNRQ1FDUUNRQQEzYSNxESEhISEhITFBATNRMSERISEhI3EjcSNxQQFQ8VNBU0FTUUEBQQExESNhISEjcSEhI3EhIWNBQQFBATNhMRETcSEhI3EhISNxI3FfAVAA0F")
        
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