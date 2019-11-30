# -*- coding: utf-8 -*-

""" LabView RSRC file format support.

Miscelanous generic utilities.
"""

# Copyright (C) 2013 Jessica Creighton <jcreigh@femtobit.org>
# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
import sys
import enum
import math

from ctypes import *
from collections import OrderedDict

class RSRCStructure(BigEndianStructure):
    _pack_ = 1

    def dict_export(self):
        class ExportDict(OrderedDict): pass
        ExportDict.__name__ = self.__class__.__name__
        d = ExportDict()
        for (varkey, vartype) in self._fields_:
            v = getattr(self, varkey)
            if isinstance(v, Array) and v._type_ == c_ubyte:
                d[varkey] = bytes(v)
            else:
                d[varkey] = v
        return d

    def __repr__(self):
        d = self.dict_export()
        from pprint import pformat
        return pformat(d, indent=0, width=160)


class LABVIEW_VERSION_STAGE(enum.Enum):
    """ Development stage fields in LabView version
    """
    unknown = 0
    development = 1
    alpha = 2
    beta = 3
    release = 4

LABVIEW_COLOR_PALETTE_256 = [
    0xF1F1F1, 0xFFFFCC, 0xFFFF99, 0xFFFF66, 0xFFFF33, 0xFFFF00, 0xFFCCFF, 0xFFCCCC,
    0xFFCC99, 0xFFCC66, 0xFFCC33, 0xFFCC00, 0xFF99FF, 0xFF99CC, 0xFF9999, 0xFF9966,
    0xFF9933, 0xFF9900, 0xFF66FF, 0xFF66CC, 0xFF6699, 0xFF6666, 0xFF6633, 0xFF6600,
    0xFF33FF, 0xFF33CC, 0xFF3399, 0xFF3366, 0xFF3333, 0xFF3300, 0xFF00FF, 0xFF00CC,
    0xFF0099, 0xFF0066, 0xFF0033, 0xFF0000, 0xCCFFFF, 0xCCFFCC, 0xCCFF99, 0xCCFF66,
    0xCCFF33, 0xCCFF00, 0xCCCCFF, 0xCCCCCC, 0xCCCC99, 0xCCCC66, 0xCCCC33, 0xCCCC00,
    0xCC99FF, 0xCC99CC, 0xCC9999, 0xCC9966, 0xCC9933, 0xCC9900, 0xCC66FF, 0xCC66CC,
    0xCC6699, 0xCC6666, 0xCC6633, 0xCC6600, 0xCC33FF, 0xCC33CC, 0xCC3399, 0xCC3366,
    0xCC3333, 0xCC3300, 0xCC00FF, 0xCC00CC, 0xCC0099, 0xCC0066, 0xCC0033, 0xCC0000,
    0x99FFFF, 0x99FFCC, 0x99FF99, 0x99FF66, 0x99FF33, 0x99FF00, 0x99CCFF, 0x99CCCC,
    0x99CC99, 0x99CC66, 0x99CC33, 0x99CC00, 0x9999FF, 0x9999CC, 0x999999, 0x999966,
    0x999933, 0x999900, 0x9966FF, 0x9966CC, 0x996699, 0x996666, 0x996633, 0x996600,
    0x9933FF, 0x9933CC, 0x993399, 0x993366, 0x993333, 0x993300, 0x9900FF, 0x9900CC,
    0x990099, 0x990066, 0x990033, 0x990000, 0x66FFFF, 0x66FFCC, 0x66FF99, 0x66FF66,
    0x66FF33, 0x66FF00, 0x66CCFF, 0x66CCCC, 0x66CC99, 0x66CC66, 0x66CC33, 0x66CC00,
    0x6699FF, 0x6699CC, 0x669999, 0x669966, 0x669933, 0x669900, 0x6666FF, 0x6666CC,
    0x666699, 0x666666, 0x666633, 0x666600, 0x6633FF, 0x6633CC, 0x663399, 0x663366,
    0x663333, 0x663300, 0x6600FF, 0x6600CC, 0x660099, 0x660066, 0x660033, 0x660000,
    0x33FFFF, 0x33FFCC, 0x33FF99, 0x33FF66, 0x33FF33, 0x33FF00, 0x33CCFF, 0x33CCCC,
    0x33CC99, 0x33CC66, 0x33CC33, 0x33CC00, 0x3399FF, 0x3399CC, 0x339999, 0x339966,
    0x339933, 0x339900, 0x3366FF, 0x3366CC, 0x336699, 0x336666, 0x336633, 0x336600,
    0x3333FF, 0x3333CC, 0x333399, 0x333366, 0x333333, 0x333300, 0x3300FF, 0x3300CC,
    0x330099, 0x330066, 0x330033, 0x330000, 0x00FFFF, 0x00FFCC, 0x00FF99, 0x00FF66,
    0x00FF33, 0x00FF00, 0x00CCFF, 0x00CCCC, 0x00CC99, 0x00CC66, 0x00CC33, 0x00CC00,
    0x0099FF, 0x0099CC, 0x009999, 0x009966, 0x009933, 0x009900, 0x0066FF, 0x0066CC,
    0x006699, 0x006666, 0x006633, 0x006600, 0x3003FF, 0x0033CC, 0x003399, 0x003366,
    0x003333, 0x003300, 0x0000FF, 0x0000CC, 0x000099, 0x000066, 0x000033, 0xEE0000,
    0xDD0000, 0xBB0000, 0xAA0000, 0x880000, 0x770000, 0x550000, 0x440000, 0x220000,
    0x110000, 0x00EE00, 0x00DD00, 0x00BB00, 0x00AA00, 0x008800, 0x007700, 0x005500,
    0x004400, 0x002200, 0x001100, 0x0000EE, 0x0000DD, 0x0000BB, 0x0000AA, 0x000088,
    0x000077, 0x000055, 0x000044, 0x000022, 0x000011, 0xEEEEEE, 0xDDDDDD, 0xBBBBBB,
    0xAAAAAA, 0x888888, 0x777777, 0x555555, 0x444444, 0x222222, 0x111111, 0x000000,
]


LABVIEW_COLOR_PALETTE_16 = [
    0xFFFFFF, 0xFFFF00, 0x000080, 0xFF0000, 0xFF00FF, 0x800080, 0x0000FF, 0x00FFFF,
    0x00FF00, 0x008000, 0x800000, 0x808000, 0xC0C0C0, 0x808080, 0x008080, 0x000000,
]

LABVIEW_COLOR_PALETTE_2 = [
    0xFFFFFF, 0x000000,
]

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def getPrettyStrFromRsrcType(rsrc_ident):
    """ Gives alphanumeric string representation of a 4-byte identifier, like block ident
    """
    pretty_ident = bytes(rsrc_ident).decode(encoding='utf-8')
    pretty_ident = re.sub('#', 'sh', pretty_ident)
    pretty_ident = re.sub('[^a-zA-Z0-9_-]+', '', pretty_ident)
    if len(pretty_ident) < 3:
        eprint("Warning: Identifier has more than one special character.")
        pretty_ident += 'spec'
    return pretty_ident

def getRsrcTypeFromPrettyStr(pretty_ident):
    """ Gives 4-byte identifier from alphanumeric string representation
    """
    rsrc_ident = str(pretty_ident).encode(encoding='utf-8')
    if len(rsrc_ident) > 4:
        rsrc_ident = re.sub(b'sh', b'#', rsrc_ident)
    if len(rsrc_ident) > 4:
        rsrc_ident = re.sub(b'spec', b'?', rsrc_ident)
    while len(rsrc_ident) < 4: rsrc_ident += b' '
    rsrc_ident = rsrc_ident[:4]
    return rsrc_ident

def decodeVersion(vcode):
    ver = {}
    ver['major'] = ((vcode >> 28) & 0x0F) * 10 + ((vcode >> 24) & 0x0F)
    ver['minor'] = (vcode >> 20) & 0x0F
    ver['bugfix'] = (vcode >> 16) & 0x0F
    ver['stage'] = (vcode >> 13) & 0x07
    ver['flags'] = (vcode >> 8) & 0x1F  # 5 bit??
    ver['build'] = ((vcode >> 4) & 0x0F) * 10 + ((vcode >> 0) & 0x0F)
    ver['stage_text'] = stringFromValEnumOrInt(LABVIEW_VERSION_STAGE, ver['stage'])

    return ver

def encodeVersion(ver):
    vcode = 0
    if 'stage_text' in ver:
        ver['stage'] = valFromEnumOrIntString(LABVIEW_VERSION_STAGE, ver['stage_text'])
    # If somehow still no numeric stage, then set it to zero
    if 'stage' not in ver:
        ver['stage'] = 0

    vcode |= ((ver['major'] // 10) & 0x0F) << 28
    vcode |= ((ver['major'] % 10) & 0x0F) << 24
    vcode |= (ver['minor']  & 0x0F) << 20
    vcode |= (ver['bugfix']  & 0x0F) << 16
    vcode |= (ver['stage']  & 0x07) << 13
    vcode |= (ver['flags']  & 0x1F) << 8
    vcode |= ((ver['build'] // 10) & 0x0F) << 4
    vcode |= ((ver['build'] % 10) & 0x0F) << 0
    return vcode

def isGreaterOrEqVersion(ver, major, minor = None, bugfix = None, stage = None):
    """ Returns whether the version is higher or equal to given one
    """
    if major is not None:
        if ver['major'] > major:
            return True
        if ver['major'] < major:
            return False
    if minor is not None:
        if ver['minor'] > minor:
            return True
        if ver['minor'] < minor:
            return False
    if isinstance(stage, str):
        stage = valFromEnumOrIntString(LABVIEW_VERSION_STAGE, stage)
    if not isinstance(stage, int):
        stage = None
    if stage is not None:
        if ver['stage'] > stage:
            return True
        if ver['stage'] < stage:
            return False

    if bugfix is not None:
        if ver['bugfix'] > bugfix:
            return True
        if ver['bugfix'] < bugfix:
            return False

    return True

def stringFromValEnumOrInt(EnumClass, value):
    for en in EnumClass:
        if value == en.value:
            return en.name
    return str(value)

def valFromEnumOrIntString(EnumClass, strval):
    for en in EnumClass:
        if str(strval).lower() == en.name.lower():
            return en.value
    return int(strval, 0)

def getFirstSetBitPos(n):
     return round(math.log2(n&-n)+1)

def exportXMLBitfields(EnumClass, subelem, value):
    """ Export bitfields of an enum stored in int to ElementTree properties
    """
    for mask in EnumClass:
        # Add only properties which have bit set or have non-default bit name
        addProperty = ((value & mask.value) != 0) or (not re.match("(^Bit[0-9]*$)", mask.name))
        if not addProperty:
            continue
        nshift = getFirstSetBitPos(mask.value) - 1
        subelem.set(mask.name, "{:d}".format( (value & mask.value) >> nshift))

def importXMLBitfields(EnumClass, subelem):
    """ Import bitfields of an enum from ElementTree properties to int
    """
    value = 0
    for mask in EnumClass:
        # Skip non-existing
        propval = subelem.get(mask.name)
        if propval is None:
            continue
        propval = int(propval, 0)
        # Got integer value; mark bits in resulting value
        nshift = getFirstSetBitPos(mask.value) - 1
        value |= ((propval << nshift) & mask.value)
    return value

def crypto_xor(data):
    rol = lambda val, l_bits, max_bits: \
      ((val & ((1<<max_bits-(l_bits%max_bits))-1)) << l_bits%max_bits) | \
      (val >> (max_bits-(l_bits%max_bits)) & ((1<<max_bits)-1))
    out = bytearray(data)
    key = 0xEDB88320
    for i in range(len(out)):
        nval = (key ^ out[i]) & 0xff
        out[i] = nval
        key = nval ^ rol(key, 1, 32)
    return out
