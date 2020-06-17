# -*- coding: utf-8 -*-

""" LabView RSRC file format support.

Miscelanous generic utilities.
"""

# Copyright (C) 2013 Jessica Creighton <jcreigh@femtobit.org>
# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

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

CHAR_TO_WORD = {
    '0': "zero", '1': "one", '2': "two", '3': "three", '4': "four", \
    '5': "five", '6': "six", '7': "seven", '8': "eight", '9': "nine",
}


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def getPrettyStrFromRsrcType(rsrc_ident):
    """ Gives alphanumeric string representation of a 4-byte identifier, like block ident
    """
    pretty_ident = bytes(rsrc_ident).decode(encoding='ascii')
    pretty_ident = re.sub('#', 'sh', pretty_ident)
    pretty_ident = re.sub('[^a-zA-Z0-9_-]+', '', pretty_ident)
    if len(pretty_ident) > 0 and pretty_ident[0] in CHAR_TO_WORD.keys():
        pretty_ident = CHAR_TO_WORD[pretty_ident[0]] + pretty_ident[1:]
    if len(pretty_ident) < 3:
        eprint("Warning: Identifier has more than one special character.")
        pretty_ident += 'spec'
    return pretty_ident

def getRsrcTypeFromPrettyStr(pretty_ident):
    """ Gives 4-byte identifier from alphanumeric string representation
    """
    if len(pretty_ident) > 4:
        pretty_ident = re.sub('sh', '#', pretty_ident)
    if len(pretty_ident) > 4:
        for c, s in CHAR_TO_WORD.items():
            if pretty_ident.startswith(s):
                pretty_ident = c + pretty_ident[len(s):]
                break
    rsrc_ident = str(pretty_ident).encode(encoding='ascii')
    if len(rsrc_ident) > 4:
        rsrc_ident = re.sub(b'spec', b'?', rsrc_ident)
    while len(rsrc_ident) < 4: rsrc_ident += b' '
    rsrc_ident = rsrc_ident[:4]
    return rsrc_ident

def enumOrIntToName(val):
    if isinstance(val, enum.IntEnum) or isinstance(val, enum.Enum):
        return val.name
    return str(val)

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

def simpleVersionFromString(vstr):
    ver = {}
    vints = [int(s) for s in vstr.split('.')]
    if len(vints) != 4: return None
    for i,key in enumerate(('major', 'minor', 'bugfix', 'build',)):
        ver[key] = vints[i]
    return ver

def simpleVersionToString(ver):
    vstr = ""
    vints = [ver[key] for key in ('major', 'minor', 'bugfix', 'build',)]
    return '.'.join(str(val) for val in vints)

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
    if bugfix is not None:
        if ver['bugfix'] > bugfix:
            return True
        if ver['bugfix'] < bugfix:
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
    return True

def isSmallerVersion(ver, *args, **kwargs):
    return not isGreaterOrEqVersion(ver, *args, **kwargs)

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

def exportXMLBitfields(EnumClass, subelem, value, skip_mask=0):
    """ Export bitfields of an enum stored in int to ElementTree properties
    """
    for mask in EnumClass:
        if ((mask.value & skip_mask) != 0): # Skip fields given as mask
            continue
        # Add only properties which have bit set or have non-default bit name
        addProperty = ((value & mask.value) != 0) or (not re.match("(^[A-Za-z]{0,3}Bit[0-9]+$)", mask.name))
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

def crypto_xor8320_decrypt(data):
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

def crypto_xor8320_encrypt(data):
    rol = lambda val, l_bits, max_bits: \
      ((val & ((1<<max_bits-(l_bits%max_bits))-1)) << l_bits%max_bits) | \
      (val >> (max_bits-(l_bits%max_bits)) & ((1<<max_bits)-1))
    out = bytearray(data)
    key = 0xEDB88320
    for i in range(len(out)):
        nval = out[i]
        out[i] = (key ^ nval) & 0xff
        key = nval ^ rol(key, 1, 32)
    return out

def zcomp_zeromsk8_decompress(data, usize):
    blocksCount = usize >> 3
    remain = usize - (blocksCount << 3)
    out = bytearray()
    dataPos = blocksCount + (1 if remain > 0 else 0)
    for blkId in range(blocksCount):
        mask = data[blkId]
        for bit in range(8):
            if (mask & (1 << bit)) != 0:
                out.append(data[dataPos])
                dataPos += 1
            else:
                out.append(0)
    if remain > 0:
        mask = data[blocksCount]
        for bit in range(remain):
            if (mask & (1 << bit)) != 0:
                out.append(data[dataPos])
                dataPos += 1
            else:
                out.append(0)
    # If size does not divide by 8, remove a few bytes at end
    return out

def zcomp_zeromsk8_compress(data):
    blocksCount = len(data) >> 3
    remain = len(data) - (blocksCount << 3)
    masks = bytearray()
    out = bytearray()
    for blkId in range(blocksCount):
        mask = 0
        for bit in range(8):
            val = data[blkId * 8 + bit]
            if val != 0:
                out.append(val)
                mask = (mask | (1 << bit))
        masks.append(mask)
    if remain > 0:
        blkId = blocksCount
        mask = 0
        for bit in range(remain):
            val = data[blkId * 8 + bit]
            if val != 0:
                out.append(val)
                mask = (mask | (1 << bit))
        masks.append(mask)
    return masks + out

def readVariableSizeFieldU2p2(bldata):
    """ Reads VI field which is either 16-bit or 32-bit, depending on first bit

    Variable size blocks are often used within RSRC files. Usually the size is
    followed by actual data.
    """
    val = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
    if (val & 0x8000) != 0: # 32-bit length
        val = ((val & 0x7FFF) << 16)
        val |= int.from_bytes(bldata.read(2), byteorder='big', signed=False)
    return val

def prepareVariableSizeFieldU2p2(val):
    """ Prepares data for VI field which is either 16-bit or 32-bit, depending on value
    """
    if val <= 0x7FFF:
        return int(val).to_bytes(2, byteorder='big', signed=False)
    else:
        return int(val | 0x80000000).to_bytes(4, byteorder='big', signed=False)
    pass

def readVariableSizeFieldS24(bldata):
    """ Reads VI field which is either 16-bit or 16+32-bit signed int, depending on first value
    """
    val = int.from_bytes(bldata.read(2), byteorder='big', signed=True)
    if val == -0x8000:
        val = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
    return val

def prepareVariableSizeFieldS24(val):
    """ Prepares data for VI field which is either 16-bit or 16+32-bit signed int, depending on value

    LV14: For some reason, the value of 0x7FFF is treated as too large even though it isn't. Not sure if this impacts all LV versions.
    """
    if val >= 0x7FFF or val < -0x8000:
        return int(-0x8000).to_bytes(2, byteorder='big', signed=True) + int(val).to_bytes(4, byteorder='big', signed=True)
    else:
        return int(val).to_bytes(2, byteorder='big', signed=True)
    pass

def readVariableSizeFieldS124(bldata):
    """ Reads VI field which is either 8, 8+16 or 8+32-bit signed int, depending on first byte
    """
    val = int.from_bytes(bldata.read(1), byteorder='big', signed=True)
    if val == -128: # 0x80
        val = int.from_bytes(bldata.read(2), byteorder='big', signed=True)
    elif val == -127: # 0x81
        val = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
    return val

def prepareVariableSizeFieldS124(val):
    """ Prepares data for VI field which is either 8, 8+16 or 8+32-bit signed int, depending on value
    """
    if val > 0x7FFF or val < -0x8000:
        return int(-128).to_bytes(1, byteorder='big', signed=True) + int(val).to_bytes(4, byteorder='big', signed=True)
    elif val > 127 or val <= -127:
        return int(-127).to_bytes(1, byteorder='big', signed=True) + int(val).to_bytes(2, byteorder='big', signed=True)
    else:
        return int(val).to_bytes(1, byteorder='big', signed=True)
    pass

def readVariableSizeFieldU124(bldata):
    """ Reads VI field which is either 8, 8+16 or 8+32-bit unsigned int, depending on first byte
    """
    val = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
    if val == 255:
        val = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
    elif val == 254:
        val = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
    return val

def prepareVariableSizeFieldU124(val):
    """ Prepares data for VI field which is either 8, 8+16 or 8+32-bit unsigned int, depending on value
    """
    if val >= 0xFFFF:
        return int(254).to_bytes(1, byteorder='big', signed=False) + int(val).to_bytes(4, byteorder='big', signed=False)
    elif val >= 0xFE:
        return int(255).to_bytes(1, byteorder='big', signed=False) + int(val).to_bytes(2, byteorder='big', signed=False)
    else:
        return int(val).to_bytes(1, byteorder='big', signed=False)
    pass

def readQuadFloat(bldata):
    """ Read quad precision float value (aka FloatExt)

    Uses Decimal module to achieve precision independent of local platform.
    """
    asint = int.from_bytes(bldata.read(16), byteorder='big', signed=False)
    sign = (-1) ** (asint >> 127) # For some reason, having the value in brackets is very important
    exponent = ((asint >> 112) & 0x7FFF) - 16383
    significand = (asint & ((1 << 112) - 1)) | (1 << 112)
    from decimal import Decimal, localcontext
    with localcontext() as ctx:
        # quad float has up to 36 digits precision, plus few for partial and sci notation margin
        ctx.prec = 39
        val = Decimal(sign) * Decimal(significand) * Decimal(2) ** (exponent - 112)
    return val

def frexpQuadFloat(d, e_largest=16384):
    """Implementation of 'frexp' for arbitrary precision decimals

    Result is a pair F, E, where 0 < F < 1 is a Decimal object,
    and E is a signed integer such that
    d = F * 2**E
    e_largest is the maximum absolute value of the exponent
    to ensure termination of the calculation

    This function was based on Simfloat code by Robert Clewley
    (robclewley@github).
    """
    from decimal import Decimal
    if d < 0:
        res = frexpQuadFloat(-d)
        return -res[0], res[1]

    elif d == 0:
        return Decimal("0"), 0

    elif d >= 1:
        w_dec = int(d)
        e_dec = 0
        while w_dec > 0 and abs(e_dec) <= e_largest:
            d /= 2
            w_dec = int(d)
            e_dec += 1
        return d, e_dec

    else:
        # 0 < d < 1
        w_dec = 0
        e_dec = 0
        while w_dec == 0 and abs(e_dec) <= e_largest:
            w_dec = int(d*2)
            if w_dec > 0:
                break
            else:
                d *= 2
                e_dec -= 1
        return d, e_dec

def prepareQuadFloat(val):
    """ Build quad precision float value (aka FloatExt)

    Uses Decimal module to achieve precision independent of local platform.
    """
    from decimal import Decimal, localcontext
    with localcontext() as ctx:
        # quad float has up to 36 digits precision, plus few for partial and sci notation margin
        ctx.prec = 39
        mantissa, exponent = frexpQuadFloat(val)
        sign = -1 if mantissa < 0 else 1
        # Properly handle exponent on zero value
        if mantissa == 0: exponent = -16382
        # Shift by one bit - because we remove the highest one from QuadFloat representation
        exponent -= 1
        significand = int(abs(mantissa) * (2 ** 113))
    asint = ((1 << 127) if sign < 0 else 0) |\
      (((exponent + 16383) & 0x7FFF) << 112) |\
      significand & ((1 << 112) - 1)
    return int(asint).to_bytes(16, byteorder='big', signed=False)

def readQualifiedName(bldata, po):
    count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
    if count > po.typedesc_list_limit:
        raise RuntimeError("Qualified name consists of {:d} string elements, limit is {:d}"\
          .format(count,po.typedesc_list_limit))
    items = [None for _ in range(count)]
    for i in range(count):
        strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        items[i] = bldata.read(strlen)
    return items

def prepareQualifiedName(items, po):
    data_buf = b''
    data_buf += int(len(items)).to_bytes(4, byteorder='big', signed=False)
    for item in items:
        data_buf += int(len(item)).to_bytes(1, byteorder='big', signed=False)
        data_buf += item
    return data_buf

def readPStr(bldata, padto, po):
    strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
    strval = bldata.read(strlen)
    uneven_len = (strlen+1) % padto # Handle padding
    if uneven_len > 0:
        bldata.read(padto - uneven_len)
    return strval

def preparePStr(strval, padto, po):
    data_buf = b''
    strlen = len(strval)
    data_buf += int(strlen).to_bytes(1, byteorder='big', signed=False)
    data_buf += bytes(strval)
    uneven_len = (strlen+1) % padto # Handle padding
    if uneven_len > 0:
        data_buf += (b'\0' * (padto - uneven_len))
    return data_buf

def readLStr(bldata, padto, po):
    strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
    if strlen > 0x20000000:
        raise RuntimeError("Long string is suspiciously long")
    strval = bldata.read(strlen)
    uneven_len = (strlen+4) % padto # Handle padding
    if uneven_len > 0:
        bldata.read(padto - uneven_len)
    return strval

def prepareLStr(strval, padto, po):
    data_buf = b''
    strlen = len(strval)
    data_buf += int(strlen).to_bytes(4, byteorder='big', signed=False)
    data_buf += bytes(strval)
    uneven_len = (strlen+4) % padto # Handle padding
    if uneven_len > 0:
        data_buf += (b'\0' * (padto - uneven_len))
    return data_buf
