#!/usr/bin/python3

import json
from copy import deepcopy
import deepdiff

USE_MOCK_PREAMPS = True

if not USE_MOCK_PREAMPS:
  import serial
  import time
  from smbus2 import SMBus
  import smbus2 as smb

# Helper functions
def encode(pydata):
  """ Encode a dictionary as JSON """
  return json.dumps(pydata)

def decode(j):
  """ Decode JSON into dictionary """
  return json.loads(j)

def parse_int(i, options):
  """ Parse an integer into one of the given options """
  if int(i) in options:
    return int(i)
  else:
    raise ValueError('{} is not in [{}]'.format(i, options))

def error(msg):
  """ wrap the error message specified by msg into an error """
  return {'error': msg}

def updated_val(update, val):
  """ get the potentially updated value, @update, defaulting to the current value, @val, if it is None """
  if update is None:
    return val, False
  else:
    return update, update != val

def clamp(x, xmin, xmax):
    return max(xmin, min(x, xmax))

# Preamp register addresses
REG_ADDRS = {
  'SRC_AD'    : 0x00,
  'CH123_SRC' : 0x01,
  'CH456_SRC' : 0x02,
  'MUTE'      : 0x03,
  'STANDBY'   : 0x04,
  'CH1_ATTEN' : 0x05,
  'CH2_ATTEN' : 0x06,
  'CH3_ATTEN' : 0x07,
  'CH4_ATTEN' : 0x08,
  'CH5_ATTEN' : 0x09,
  'CH6_ATTEN' : 0x0A
}
PREAMPS = [0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38, 0x40, 0x48, 0x50, 0x58, 0x60, 0x68, 0x70, 0x78]

class MockPreamps:
  def __init__(self):
    self.preamps = dict()

  def new_preamp(self, index):
    self.preamps[index] = [ 0x0 ] * len(REG_ADDRS)

  def write_byte_data(self, preamp_addr, reg, data):
    assert preamp_addr in PREAMPS
    assert type(preamp_addr) == int
    assert type(reg) == int
    assert type(data) == int
    # dynamically update preamps
    if preamp_addr not in self.preamps:
      self.new_preamp(preamp_addr)
    print("writing to 0x{:02x} @ 0x{:02x} with 0x{:02x}".format(preamp_addr, reg, data))
    self.preamps[preamp_addr][reg] = data

  def print_regs(self):
    for preamp, regs in self.preamps.items():
      print('preamp {}:'.format(preamp / 8))
      for reg, val in enumerate(regs):
        print('  {} - {:02b}'.format(reg, val))

  def print(self):
    for preamp_addr in self.preamps.keys():
      preamp = int(preamp_addr / 8)
      print('preamp {}:'.format(preamp))
      for src in range(4):
        # TODO: print source configurations
        pass
      for zone in range(6):
        self.print_zone_state(6 * (preamp - 1) + zone)

  def vol_string(self, vol):
    MAX_VOL = 0
    MIN_VOL = -79
    VOL_RANGE = MAX_VOL - MIN_VOL + 1
    VOL_STR_LEN = 20
    VOL_SCALE = VOL_RANGE / VOL_STR_LEN
    vol_level = int((vol - MIN_VOL)  / VOL_SCALE)
    assert vol_level >= 0 and vol_level < VOL_STR_LEN
    vol_string = ['-'] * VOL_STR_LEN
    vol_string[vol_level] = '|' # place the volume slider bar at its current spot
    return ''.join(vol_string) # turn that char array into a string

  def print_zone_state(self, zone):
    assert zone >= 0
    preamp = (int(zone / 6) + 1) * 8
    z = zone % 6
    regs = self.preamps[preamp]
    src = ((regs[REG_ADDRS['CH456_SRC']] << 8) | regs[REG_ADDRS['CH123_SRC']] >> 3 * z) & 0b111
    vol = -regs[REG_ADDRS['CH1_ATTEN'] + z]
    stby = (regs[REG_ADDRS['STANDBY']] & (1 << z)) > 0
    muted = (regs[REG_ADDRS['MUTE']] & (1 << z)) > 0
    state = []
    if muted:
      state += ['muted']
    if stby:
      state += ['in standby']
    print('  source {} --> zone {} vol [{}], {}'.format(src, zone, self.vol_string(vol), ','.join(state)))

class MockRt:
  """ Mock of an EthAudio Runtime

      This pretends to be the runtime of EthAudio, but actually does nothing
  """

  def __init__(self):
    pass

  def update_sources(self, digital):
    """ modify all of the 4 system sources

      Args:
        digital [bool*4]: array of configuration for sources where
          Analog is False and Digital True

      Returns:
        True on success, False on hw failure
    """
    assert len(digital) == 4
    for d in digital:
      assert type(d) == bool
    return True

  def update_zone_mutes(self, zone, mutes):
    """ Update the mute level to all of the zones

      Args:
        zone int: zone to muted/unmute
        mutes [bool*zones]: array of configuration for zones where
          Unmuted is False and Muted True

      Returns:
        True on success, False on hw failure
    """
    assert len(mutes) >= 6
    num_preamps = int(len(mutes) / 6)
    assert len(mutes) == num_preamps * 6
    for preamp in range(num_preamps):
      for zone in range(6):
        assert type(mutes[preamp * 6 + zone]) == bool
    return True

  def update_zone_stbys(self, zone, stbys):
    """ Update the standby to all of the zones

      Args:
        zone int: zone to standby/unstandby
        stbys [bool*zones]: array of configuration for zones where
          On is False and Standby True

      Returns:
        True on success, False on hw failure
    """
    assert len(stbys) >= 6
    num_preamps = int(len(stbys) / 6)
    assert len(stbys) == num_preamps * 6
    for preamp in range(num_preamps):
      for zone in range(6):
        assert type(stbys[preamp * 6 + zone]) == bool
    return True

  def update_zone_sources(self, zone, sources):
    """ Update the sources to all of the zones

      Args:
        zone int: zone to change source
        sources [int*zones]: array of source ids for zones (None in place of source id indicates disconnect)

      Returns:
        True on success, False on hw failure
    """
    assert len(sources) >= 6
    num_preamps = int(len(sources) / 6)
    assert len(sources) == num_preamps * 6
    for preamp in range(num_preamps):
      for zone in range(6):
        src = sources[preamp * 6 + zone]
        assert type(src) == int or src == None
    return True

  def update_zone_vol(self, zone, vol):
    """ Update the sources to all of the zones

      Args:
        zone: zone to adjust vol
        vol: int in range[-79, 0]

      Returns:
        True on success, False on hw failure
    """
    preamp = zone // 6
    assert zone >= 0
    assert preamp >= 0 and preamp <= 15
    assert vol <= 0 and vol >= -79
    return True

class RpiRt:
  """ Actual EthAudio Runtime

      This acts as an EthAudio Runtime, expected to be executed on a raspberrypi
  """

  def __init__(self):
    # TODO: merge mock and actual preamp writing
    if not USE_MOCK_PREAMPS:
      # Setup serial connection via UART pins - set I2C addresses for preamps
      # ser = serial.Serial ("/dev/ttyS0") <--- for RPi4!
      ser = serial.Serial ("/dev/ttyAMA0")
      ser.baudrate = 9600
      addr = 0x41, 0x10, 0x0D, 0x0A
      ser.write(addr)
      ser.close()

      # Delay to account for addresses being set
      # Possibly unnecessary due to human delay
      time.sleep(1)

      # Setup self._bus as I2C1 from the RPi
      bus = smb.SMBus(1)
    else:
      bus = MockPreamps()
    self._bus = bus

  def update_zone_mutes(self, zone, mutes):
    """ Update the mute level to all of the zones

      Args:
        zone int: zone to muted/unmute
        mutes [bool*zones]: array of configuration for zones where
          Unmuted is False and Muted True

      Returns:
        True on success, False on hw failure
    """
    assert len(mutes) >= 6
    num_preamps = int(len(mutes) / 6)
    assert len(mutes) == num_preamps * 6
    preamp = zone // 6
    mute_cfg = 0x00
    for z in range(6):
      assert type(mutes[preamp * 6 + z]) == bool
      if mutes[preamp * 6 + z]:
        mute_cfg = mute_cfg | (0x01 << z)
      self._bus.write_byte_data(PREAMPS[preamp], REG_ADDRS['MUTE'], mute_cfg)

    # TODO: Add error checking on successful write
    return True

  def update_zone_stbys(self, zone, stbys):
    """ Update the standby to all of the zones

      Args:
        zone int: zone to standby/unstandby
        stbys [bool*zones]: array of configuration for zones where
          On is False and Standby True

      Returns:
        True on success, False on hw failure
    """
    assert len(stbys) >= 6
    num_preamps = int(len(stbys) / 6)
    assert len(stbys) == num_preamps * 6
    preamp = zone // 6
    stby_cfg = 0x00
    for z in range(6):
      assert type(stbys[preamp * 6 + z]) == bool
      if stbys[preamp * 6 + z]:
        stby_cfg = stby_cfg | (0x01 << z)
    self._bus.write_byte_data(PREAMPS[preamp], REG_ADDRS['STANDBY'], stby_cfg)

    # TODO: Add error checking on successful write
    return True

  def update_zone_sources(self, zone, sources):
    """ Update the sources to all of the zones

      Args:
        zone int: zone to change source
        sources [int*zones]: array of source ids for zones (None in place of source id indicates disconnect)

      Returns:
        True on success, False on hw failure
    """
    assert len(sources) >= 6
    num_preamps = int(len(sources) / 6)
    assert len(sources) == num_preamps * 6
    preamp = zone // 6

    source_cfg123 = 0x00
    source_cfg456 = 0x00
    for z in range(6):
      src = sources[preamp * 6 + z]
      assert type(src) == int or src == None
      if z < 3:
        source_cfg123 = source_cfg123 | (src << (z*2))
      else:
        source_cfg456 = source_cfg456 | (src << ((z-3)*2))
    self._bus.write_byte_data(PREAMPS[preamp], REG_ADDRS['CH123_SRC'], source_cfg123)
    self._bus.write_byte_data(PREAMPS[preamp], REG_ADDRS['CH456_SRC'], source_cfg456)

    # TODO: Add error checking on successful write
    return True

  def update_zone_vol(self, zone, vol):
    """ Update the volume to the specific zone

      Args:
        zone: zone to adjust vol
        vol: int in range[-79, 0]

      Returns:
        True on success, False on hw failure
    """
    preamp = int(zone / 6) # int(x/y) does the same thing as (x // y)
    assert zone >= 0
    assert preamp < 15
    assert vol <= 0 and vol >= -79

    chan = zone - (preamp * 6)
    hvol = abs(vol)

    chan_reg = REG_ADDRS['CH1_ATTEN'] + chan
    self._bus.write_byte_data(PREAMPS[preamp], chan_reg, hvol)

    # TODO: Add error checking on successful write
    return True

  def update_sources(self, digital):
    """ modify all of the 4 system sources

      Args:
        digital [bool*4]: array of configuration for sources where
          Analog is False and Digital True

      Returns:
        True on success, False on hw failure
    """

    # Start with a fresh byte - only update on Digital (True)
    output = 0x00

    # When digital is true, set the appropriate bit to 1
    assert len(digital) == 4
    for d in digital:
      assert type(d) == bool

    for i in range(4):
      if digital[i]:
        output = output | (0x01 << i)

    # Send out the updated source information to the appropriate preamp
    self._bus.write_byte_data(PREAMPS[0], REG_ADDRS['SRC_AD'], output)

    # TODO: update this to allow for different preamps on the bus
    # TODO: Add error checking on successful write
    return True


class EthAudioApi:
  """ EthAudio API

    TODO: make this either a base class, put it in another file, and make both a mock class and a real implementation
    For now this is just a mock implementation
   """

  def __init__(self, rt = MockRt()):
    self._rt = rt
    """ intitialize the mock system to to base configuration """
    # TODO: this status will need to be loaded from a file
    self.status = { # This is the system state response that will come back from the ethaudio box
      "sources": [ # this is an array of source objects, each has an id, name, and bool specifying wheater source comes from RCA or digital input
        { "id": 0, "name": "Source 1", "digital": False  },
        { "id": 1, "name": "Source 2", "digital": False  },
        { "id": 2, "name": "Source 3", "digital": False  },
        { "id": 3, "name": "Source 4", "digital": False  }
      ],
      "zones": [ # this is an array of zones, array length depends on # of boxes connected
        { "id": 0,  "name": "Zone 1",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 1,  "name": "Zone 2",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 2,  "name": "Zone 3",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 3,  "name": "Zone 4",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 4,  "name": "Zone 5",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 5,  "name": "Zone 6",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 6,  "name": "Zone 7",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 7,  "name": "Zone 8",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 8,  "name": "Zone 9",  "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 9,  "name": "Zone 10", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 10, "name": "Zone 11", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 11, "name": "Zone 12", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 12, "name": "Zone 13", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 13, "name": "Zone 14", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 14, "name": "Zone 15", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 15, "name": "Zone 16", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 16, "name": "Zone 17", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 },
        { "id": 17, "name": "Zone 18", "source_id": 0, "mute": True, 'stby': True, "disabled": False, "vol": -79 }
      ],
      "groups": [ # this is an array of groups that have been created , each group has a friendly name and an array of member zones
        { "id": 0, "name": "Group 1", "zones": [0,1,2] },
        { "id": 1, "name": "Group 2", "zones": [2,3,4] },
        { "id": 2, "name": "Group 3", "zones": [5] }
      ]
    }

  def parse_cmd(self, cmd):
    """ process an individual command

      Args:
        cmd(dict): a command decoded from the JSON interface
      Returns:
        'None' if successful, otherwise an error(dict)
    """
    try:
      command = cmd['command']
      if command is None:
        output = error('No command specified')
      elif command == 'return_state':
        output = None # state is returned at a higher level on success
      elif command == 'set_source':
        output = self.set_source(cmd.get('id'), cmd.get('name'), cmd.get('digital'))
      elif command == 'set_zone':
        output = self.set_zone(cmd.get('id'), cmd.get('name'), cmd.get('source_id'), cmd.get('mute'), cmd.get('stby'), cmd.get('vol'), cmd.get('disabled'))
      elif command == 'set_group':
        output = self.set_group(cmd.get('id'), cmd.get('name'), cmd.get('source_id'), cmd.get('zones'), cmd.get('mute'), cmd.get('stby'), cmd.get('vol_delta'))
      elif command == 'create_group':
        output = self.create_group(cmd.get('name'), cmd.get('zones'))
      elif command == 'delete_group':
        output = self.delete_group(cmd.get('id'))
      else:
        output = error('command {} is not supported'.format(command))

      return output
    except Exception as e:
      return error(str(e)) # TODO: handle exception more verbosely

  def get_state(self):
    """ get the system state (dict) """
    return self.status

  def set_source(self, id, name = None, digital = None):
    """ modify any of the 4 system sources

      Args:
        id (int): source id [0,4]
        name (str): user friendly source name, ie. "cd player" or "stream 1"

      Returns:
        'None' on success, otherwise error (dict)
    """
    idx = None
    for i, s in enumerate(self.status['sources']):
      if s['id'] == id:
        idx = i
    if idx is not None:
      try:
        src = self.status['sources'][idx]
        name, _ = updated_val(name, src['name'])
        digital, _ = updated_val(digital, src['digital'])
      except Exception as e:
        return error('failed to set source, error getting current state: {}'.format(e))
      try:
        # get the current digital state of all of the sources
        digital_cfg = [ self.status['sources'][s]['digital'] for s in range(4) ]
        # update this source
        digital_cfg[idx] = bool(digital)
        # update the name
        src['name'] = str(name)
        if self._rt.update_sources(digital_cfg):
          # update the status
          src['digital'] = bool(digital)
          if USE_MOCK_PREAMPS and type(self._rt) == RpiRt:
            self._rt._bus.print()
          return None
        else:
          return error('failed to set source')
      except Exception as e:
        return error('set source ' + str(e))
    else:
      return error('set source: index {} out of bounds'.format(idx))

  def set_zone(self, id, name=None, source_id=None, mute=None, stby=None, vol=None, disabled=None):
    """ modify any zone

          Args:
            id (int): any valid zone [0,p*6-1] (6 zones per preamp)
            name(str): friendly name for the zone, ie "bathroom" or "kitchen 1"
            source_id (int): source to connect to [0,4]
            mute (bool): mute the zone regardless of set volume
            stby (bool): set the zone to standby, very low power consumption state
            vol (int): attenuation [-79,0] 0 is max volume, -79 is min volume
            disabled (bool): disable zone, for when the zone is not connected to any speakers and not in use
          Returns:
            'None' on success, otherwise error (dict)
    """
    idx = None
    for i, s in enumerate(self.status['zones']):
      if s['id'] == id:
        idx = i
    if idx is not None:
      try:
        z = self.status['zones'][idx]
        # TODO: use updated? value
        name, _ = updated_val(name, z['name'])
        source_id, update_source_id = updated_val(source_id, z['source_id'])
        mute, update_mutes = updated_val(mute, z['mute'])
        stby, update_stbys = updated_val(stby, z['stby'])
        vol, update_vol = updated_val(vol, z['vol'])
        disabled, _ = updated_val(disabled, z['disabled'])
      except Exception as e:
        return error('failed to set zone, error getting current state: {}'.format(e))
      try:
        sid = parse_int(source_id, [0, 1, 2, 3, 4])
        vol = parse_int(vol, range(-79, 1))
        zones = self.status['zones']
        # update non hw state
        z['name'] = name
        z['disabled'] = disabled
        # TODO: figure out an order of operations here, like does mute need to be done before changing sources?
        if True or update_source_id:
          zone_sources = [ zone['source_id'] for zone in zones ]
          zone_sources[idx] = sid
          if self._rt.update_zone_sources(idx, zone_sources):
            z['source_id'] = sid
          else:
            return error('set zone failed: unable to update zone source')
        if update_mutes:
          mutes = [ zone['mute'] for zone in zones ]
          mutes[idx] = mute
          if self._rt.update_zone_mutes(idx, mutes):
            z['mute'] = mute
          else:
            return error('set zone failed: unable to update zone mute')
        if update_stbys:
          stbys = [ zone['stby'] for zone in zones ]
          stbys[idx] = stby
          if self._rt.update_zone_stbys(idx, stbys):
            z['stby'] = stby
          else:
            return error('set zone failed: unable to update zone stby')
        if update_vol:
          if self._rt.update_zone_vol(idx, vol):
            z['vol'] = vol
            if vol > -79:
              z['stby'] = False
              z['mute'] = False
            else:
              z['stby'] = True
              z['mute'] = True
          else:
            return error('set zone failed: unable to update zone volume')

        if USE_MOCK_PREAMPS and type(self._rt) == RpiRt:
          self._rt._bus.print()
        return None
      except Exception as e:
        return error('set zone: '  + str(e))
    else:
        return error('set zone: index {} out of bounds'.format(idx))

  def get_group(self, id):
    for i, g in enumerate(self.status['groups']):
      if g['id'] == id:
        return i,g
    return -1, None

  def set_group(self, id, name=None, source_id=None, zones=None, mute=None, stby=None, vol_delta=None):
    """ Configure an existing group
        parameters will be used to configure each sone in the group's zones
        all parameters besides the group id, @id, are optional
    """
    _, g = self.get_group(id)
    if g is None:
      return error('set group failed, group {} not found'.format(id))
    try:
      name, _ = updated_val(name, g['name'])
      zones, _ = updated_val(zones, g['zones'])
    except Exception as e:
      return error('failed to configure group, error getting current state: {}'.format(e))
    g['name'] = name
    g['zones'] = zones
    for z in [ self.status['zones'][zone] for zone in zones ]:
      if vol_delta is not None:
        vol = clamp(z['vol'] + vol_delta, -79, 0)
      else:
        vol = None
      self.set_zone(z['id'], None, source_id, mute, stby, vol)

    if USE_MOCK_PREAMPS and type(self._rt) == RpiRt:
      self._rt._bus.print()

  def new_group_id(self):
    """ get next available group id """
    ids = [ g['id'] for g in self.status['groups'] ]
    ids = set(ids) # simpler/faster access
    new_gid = len(ids)
    for i in range(0, len(ids)):
      if i not in ids:
        new_gid = i
        break
    return new_gid

  def create_group(self, name, zones):
    """create a new group with a list of zones
    Refer to the returned system state to obtain the id for the newly created group
    """
    # verify new group's name is unique
    names = [ g['name'] for g in self.status['groups'] ]
    if name in names:
      return error('create group failed: {} already exists'.format(name))

    # get the new groug's id
    id = self.new_group_id()

    # add the new group
    group = { 'id': id, 'name' : name, 'zones' : zones }
    self.status['groups'].append(group)

  def delete_group(self, id):
    """delete an existing group"""
    try:
      i, _ = self.get_group(id)
      del self.status['groups'][i]
    except KeyError:
      return error('delete group failed: {} does not exist'.format(id))
