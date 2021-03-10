#!/usr/bin/python3
import sys
import time
import re

# Check out https://github.com/hzeller/upnp-display/blob/master/controller-state.cc
# This controller state allows subscribing to song info from a UPnP source

args = sys.argv[1:]
print('Input Arguments: {}'.format(args[0]))
try:
    src = int(args[0])
    loc = '/home/pi/config/dlna/{}/'.format(src)
except:
    print('Error: Invalid source choice. Sources range from 0 to 3. Please try again.')
    sys.exit('Failure.')
print('Targeting {}'.format(loc))
cs_loc = loc + 'currentSong'
cs_conf = {
    'TransportState': 'PLAYING'
}
ctmd = re.compile(r'dc:(.*?)>(.*?)</dc:|upnp:(.*?)>(.*?)</upnp:')
ts = re.compile(r'TransportState: ([A-Z\S]*)')

def read_field():
    line = sys.stdin.readline()
    line = line.strip('\n')
    if line[0:4] == "INFO":
        s1 = line.split('] ')
        return s1[1]
    else:
        return None

def meta_parser(fstring):
    u = {}
    for m in ts.finditer(fstring):
        if m[1]:
            u['TransportState'] = m[1]
    for n in ctmd.finditer(fstring):
        if n[1]:
            u[n[1]] = n[2]
        else:
            u[n[3]] = n[4]
    return u

f = open(cs_loc, 'w')
f.write("")
f.close()

while True:
    field = read_field()
    if field:
        cs_conf.update(meta_parser(field))
        print(cs_conf)
        f = open(cs_loc, 'w')
        f.write(str(cs_conf))
        f.close()
