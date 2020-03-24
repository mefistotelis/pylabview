# -*- coding: utf-8 -*-

""" LabView RSRC file format data fill.

    Implements storage of data which maps to types defined within VI.
"""

# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.


import enum
import struct

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from ctypes import *

from LVmisc import *
import LVclasses
import LVconnector
import LVconnectorref


class DataFill:
    def __init__(self, vi, idx, tm_flags, td, po):
        """ Creates new DataFill object, capable of handling generic data.
        """
        self.vi = vi
        self.po = po
        self.index = idx
        self.tm_flags = tm_flags
        self.td = td
        self.value = None
        self.raw_data = None
        # Whether RAW data has been updated and RSRC parsing is required to update properties
        self.raw_data_updated = False
        # Whether any properties have been updated and preparation of new RAW data is required
        self.parsed_data_updated = False

    def isRefnumTag(self, td):
        """ Returns if given refnum td is a tag type.
        """
        from LVconnectorref import REFNUM_TYPE
        if td.refType() in (REFNUM_TYPE.IVIRef,REFNUM_TYPE.VisaRef,\
          REFNUM_TYPE.UsrDefTagFlt,REFNUM_TYPE.UsrDefndTag,):
            return True
        return False

    def isSpecialDSTMClusterElement(self, idx, tm_flags):
        ver = self.vi.getFileVersion()

        if (tm_flags & 0x0004) != 0:
            if isSmallerVersion(ver, 10,0,0,2):
                if idx == 2:
                    return True
            else:
                if idx == 1:
                    return True
            return False
        if (tm_flags & 0x0010) != 0:
            if idx in (1,2,3,):
                return True
        elif (tm_flags & 0x0020) != 0:
            if idx == 3:
                return True
        elif (tm_flags & 0x0040) != 0:
            if idx == 2:
                return True
        return False

    def initWithRSRC(self, bldata):
        self.initWithRSRCParse(bldata)
        if (self.po.verbose > 2):
            fulltype = self.td.fullType()
            print("{:s}: {} Data fill for type {} value {} offs after {}"\
              .format(self.vi.src_fname, type(self).__name__,\
               fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,\
               self.value, bldata.tell()))
        pass

    def prepareDict(self):
        return { 'value': self.value }

    def __repr__(self):
        d = self.prepareDict()
        from pprint import pformat
        return type(self).__name__ + pformat(d, indent=0, compact=True, width=512)


class DataFillVoid(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = None


class DataFillInt(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.base = 10
        from LVconnector import CONNECTOR_FULL_TYPE
        fulltype = self.td.fullType()
        if fulltype in (CONNECTOR_FULL_TYPE.NumInt8,):
            self.size = 1
            self.signed = True
        elif fulltype in (CONNECTOR_FULL_TYPE.NumInt16,):
            self.size = 2
            self.signed = True
        elif fulltype in (CONNECTOR_FULL_TYPE.NumInt32,):
            self.size = 4
            self.signed = True
        elif fulltype in (CONNECTOR_FULL_TYPE.NumInt64,):
            self.size = 8
            self.signed = True
        elif fulltype in (CONNECTOR_FULL_TYPE.NumUInt8,):
            self.size = 1
            self.signed = False
        elif fulltype in (CONNECTOR_FULL_TYPE.NumUInt16,):
            self.size = 2
            self.signed = False
        elif fulltype in (CONNECTOR_FULL_TYPE.NumUInt32,):
            self.size = 4
            self.signed = False
        elif fulltype in (CONNECTOR_FULL_TYPE.NumUInt64,):
            self.size = 8
            self.signed = False
        elif fulltype in (CONNECTOR_FULL_TYPE.UnitUInt8,):
            self.size = 1
            self.signed = False
        elif fulltype in (CONNECTOR_FULL_TYPE.UnitUInt16,):
            self.size = 2
            self.signed = False
        elif fulltype in (CONNECTOR_FULL_TYPE.UnitUInt32,):
            self.size = 4
            self.signed = False
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__,\
               fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype))

    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(self.size), byteorder='big', signed=self.signed)


class DataFillFloat(DataFill):
    def initWithRSRCParse(self, bldata):
        from LVconnector import CONNECTOR_FULL_TYPE
        fulltype = self.td.fullType()
        if fulltype in (CONNECTOR_FULL_TYPE.NumFloat32,CONNECTOR_FULL_TYPE.UnitFloat32,):
            self.value = struct.unpack('>f', bldata.read(4))
        elif fulltype in (CONNECTOR_FULL_TYPE.NumFloat64,CONNECTOR_FULL_TYPE.UnitFloat64,):
            self.value = struct.unpack('>d', bldata.read(8))
        elif fulltype in (CONNECTOR_FULL_TYPE.NumFloatExt,CONNECTOR_FULL_TYPE.UnitFloatExt,):
            self.value = readQuadFloat(bldata)
        elif fulltype in (CONNECTOR_FULL_TYPE.NumComplex64,CONNECTOR_FULL_TYPE.UnitComplex64,):
            self.value = struct.unpack('>ff', bldata.read(8))
        elif fulltype in (CONNECTOR_FULL_TYPE.NumComplex128,CONNECTOR_FULL_TYPE.UnitComplex128,):
            self.value = struct.unpack('>dd', bldata.read(16))
        elif fulltype in (CONNECTOR_FULL_TYPE.NumComplexExt,CONNECTOR_FULL_TYPE.UnitComplexExt,):
            self.value = (readQuadFloat(bldata),readQuadFloat(bldata),)
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__,\
               fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype))


class DataFillBool(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        from LVconnector import CONNECTOR_FULL_TYPE
        fulltype = self.td.fullType()
        if fulltype in (CONNECTOR_FULL_TYPE.BooleanU16,):
            self.size = 2
        elif fulltype in (CONNECTOR_FULL_TYPE.Boolean,):
            ver = self.vi.getFileVersion()
            if isGreaterOrEqVersion(ver, 4,5,0):
                self.size = 1
            else:
                self.size = 2
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__,\
               fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype))

    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(self.size), byteorder='big', signed=False)


class DataFillString(DataFill):
    def initWithRSRCParse(self, bldata):
        strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        #if self.td.prop1 != 0xffffffff: # in such case part of the value might be irrelevant, as only
        # part to the size (self.td.prop1 & 0x7fffffff) is used; but the length stored is still valid
        self.value = bldata.read(strlen)


class DataFillPath(DataFill):
    def initWithRSRCParse(self, bldata):
        startPos = bldata.tell()
        clsident = bldata.read(4)
        if clsident == b'PTH0':
            self.value = LVclasses.LVPath0(self.vi, self.po)
        elif clsident in (b'PTH1', b'PTH2',):
            self.value = LVclasses.LVPath1(self.vi, self.po)
        else:
            fulltype = self.td.fullType()
            raise RuntimeError("Data fill contains path data of unrecognized class {}"\
              .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype))
        bldata.seek(startPos)
        self.value.parseRSRCData(bldata)


class DataFillCString(DataFill):
    def initWithRSRCParse(self, bldata):
        # No idea why sonething which looks like string type stores 32-bit value instead
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)


class DataFillArray(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.dimensions = []

    def initWithRSRCParse(self, bldata):
        self.dimensions = []
        for dim in self.td.dimensions:
            val = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.dimensions.append(val)
        # Multiply sizes of each dimension to get total number of items
        totItems = 1
        # TODO Not sure if the amount are in self.td.dimensions or self.dimensions; maybe they need to be same?
        for dim in self.dimensions:
            totItems *= dim & 0x7fffffff
        self.value = []
        VCTP = self.vi.get_or_raise('VCTP')
        sub_td = VCTP.getFlatType(self.td.clients[0].index)
        #if sub_td.fullType() in (CONNECTOR_FULL_TYPE.Boolean,) and isSmallerVersion(ver, 4,5,0,1): # TODO expecting special case, never seen it though
        if totItems > self.po.connector_list_limit * len(self.dimensions):
                fulltype = self.td.fullType()
                raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
                  .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,\
                  totItems, self.po.connector_list_limit * len(self.dimensions)))
        for i in range(totItems):
            try:
                sub_df = newDataFillObject(self.vi, self.td.clients[0].index, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                fulltype = sub_td.fullType()
                raise RuntimeError("Data type {}: {}"\
                  .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,str(e)))
        pass


class DataFillArrayDataPtr(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)


class DataFillCluster(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = []
        for cli_idx, conn_idx, conn_obj, conn_flags in self.td.clientsEnumerate():
            try:
                sub_df = newDataFillObject(self.vi, conn_idx, self.tm_flags, conn_obj, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                fulltype = conn_obj.fullType()
                raise RuntimeError("Data type {}: {}"\
                  .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,str(e)))
            pass


class DataFillLVVariant(DataFill):
    def initWithRSRCParse(self, bldata):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 6,0,0,2):
            self.value = LVclasses.LVVariant(0, self.vi, self.po, useConsolidatedTypes=True, allowFillValue=True)
        else:
            self.value = LVclasses.OleVariant(0, self.vi, self.po)
        self.value.parseRSRCData(bldata)


class DataFillMeasureData(DataFill):
    def initWithRSRCParse(self, bldata):
        #if self.td.dtFlavor() in (MEASURE_DATA_FLAVOR.TimeStamp,):
        self.value = None # TODO implement
        raise NotImplementedError("MeasureData default value read is not implemented")


class DataFillComplexFixedPt(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.value = 2 * [None]
        self.vflags = 2 * [None]

    def initWithRSRCParse(self, bldata):
        # Not sure about the order of values in this type
        self.value = 2 * [None]
        self.vflags = 2 * [None]
        for i in range(2):
            self.value[i] = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
            if self.td.allocOv:
                self.vflags[i] = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        pass


class DataFillFixedPoint(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.vflags = None

    def initWithRSRCParse(self, bldata):
        self.value = bldata.read(self.td.blkSize)


class DataFillBlock(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)


class DataFillRepeatedBlock(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = []
        VCTP = self.vi.get_or_raise('VCTP')
        sub_td = VCTP.getFlatType(self.td.typeFlatIdx)
        if self.td.numRepeats > self.po.connector_list_limit:
            fulltype = self.td.fullType()
            raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
              .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,\
              self.td.numRepeats, self.po.connector_list_limit))
        for i in range(self.td.numRepeats):
            try:
                sub_df = newDataFillObject(self.vi, self.td.typeFlatIdx, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                fulltype = sub_td.fullType()
                raise RuntimeError("Data type {}: {}"\
                  .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,str(e)))
        pass


class DataFillAll(DataFill):
    def initWithRSRCParse(self, bldata):
        from LVconnector import CONNECTOR_FULL_TYPE
        fulltype = self.td.fullType()
        if fulltype in (CONNECTOR_FULL_TYPE.Refnum,):
            from LVconnectorref import REFNUM_TYPE
            if self.td.refType() in (REFNUM_TYPE.IVIRef,REFNUM_TYPE.VisaRef,REFNUM_TYPE.Imaq,):
                # These ref types represent IORefnum
                ver = self.vi.getFileVersion()
                if isGreaterOrEqVersion(ver, 6,0,0):
                    if self.isRefnumTag(self.td):
                        strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                        self.value = bldata.read(strlen)
                    else:
                        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                else:
                    self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            elif self.td.refType() in (REFNUM_TYPE.UsrDefTagFlt,REFNUM_TYPE.UsrDefndTag,):
                # These ref types represent Tag subtypes of UDRefnum
                ver = self.vi.getFileVersion()
                strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.value = bldata.read(strlen)
                if isGreaterOrEqVersion(ver, 12,0,0,2) and isSmallerVersion(ver, 12,0,0,5):
                    bldata.read(1)
                if self.td.refType() in (REFNUM_TYPE.UsrDefTagFlt,):
                    strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                    self.usrdef1 = bldata.read(strlen)
                    strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                    self.usrdef2 = bldata.read(strlen)
                    self.usrdef3 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                    strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                    self.usrdef4 = bldata.read(strlen)
            elif self.td.refType() in (REFNUM_TYPE.UsrDefined,):
                # These ref types represent Non-tag subtypes of UDRefnum
                self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            elif self.td.refType() in (REFNUM_TYPE.UDClassInst,):
                self.value = []
                numLevels = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                self.libName = bldata.read(strlen)
                if (bldata.tell() % 4) > 0:
                    bldata.read(4 - (bldata.tell() % 4)) # Padding bytes
                if numLevels > self.po.connector_list_limit:
                    fulltype = self.td.fullType()
                    raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
                      .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,\
                      numLevels, self.po.connector_list_limit))
                for i in range(numLevels):
                    datalen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                    libVersion = bldata.read(datalen)
                    self.value.append(libVersion)
            else:
                # All the normal refnums
                # The format seem to be different for LV6.0.0 and older, but still 4 bytes
                self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        elif fulltype in (CONNECTOR_FULL_TYPE.Ptr,):
            ver = self.vi.getFileVersion()
            if isSmallerVersion(ver, 8,6,0,1):
                self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            else:
                self.value = None
        elif fulltype in (CONNECTOR_FULL_TYPE.PtrTo,):
            self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        elif fulltype in (CONNECTOR_FULL_TYPE.ExtData,):
            eprint("{:s}: Warning: Data fill asks to read default value of {} type, this is not implemented."\
              .format(self.vi.src_fname, fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype))
            self.value = None
        elif fulltype in (CONNECTOR_FULL_TYPE.Function,CONNECTOR_FULL_TYPE.SubArray,):
            eprint("{:s}: Warning: Data fill asks to read default value of {} type, this should never happen."\
              .format(self.vi.src_fname, fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype))
            self.value = None
        elif fulltype in (CONNECTOR_FULL_TYPE.TypeBlock,):
            self.value = []
            # We expect only one client within TypeDef
            for client in self.td.clients:
                try:
                    sub_df = newDataFillObject(self.vi, -1, self.tm_flags, client.nested, self.po)
                    self.value.append(sub_df)
                    sub_df.initWithRSRC(bldata)
                except Exception as e:
                    fulltype = client.nested.fullType()
                    raise RuntimeError("Data type {}: {}"\
                      .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,str(e)))
                pass
        elif fulltype in (CONNECTOR_FULL_TYPE.TypeDef,):
            self.value = []
            # We expect only one client within TypeDef
            for client in self.td.clients:
                try:
                    sub_df = newDataFillObject(self.vi, -1, self.tm_flags, client.nested, self.po)
                    self.value.append(sub_df)
                    sub_df.initWithRSRC(bldata)
                except Exception as e:
                    fulltype = client.nested.fullType()
                    raise RuntimeError("Data type {}: {}"\
                      .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,str(e)))
                pass
        elif fulltype in (CONNECTOR_FULL_TYPE.SubString,CONNECTOR_FULL_TYPE.PolyVI,):
            # This would cause silently ignored error in LV14
            self.value = None
        else:
            self.value = None
        pass


class SpecialDSTMCluster(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = []
        skipNextEntry = ((self.tm_flags & 0x0200) != 0)
        for cli_idx, conn_idx, conn_obj, conn_flags in self.td.clientsEnumerate():
            if not self.isSpecialDSTMClusterElement(cli_idx, self.tm_flags):
                continue
            if skipNextEntry:
                skipNextEntry = False
                continue
            try:
                sub_df = newDataFillObject(self.vi, conn_idx, self.tm_flags, conn_obj, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                fulltype = conn_obj.fullType()
                raise RuntimeError("Data type {}: {}"\
                  .format(fulltype.name if isinstance(fulltype, enum.IntEnum) else fulltype,str(e)))
            pass
        pass


def newDataFillObject(vi, idx, tm_flags, td, po):
    """ Creates and returns new data fill object with given parameters
    """
    from LVconnector import CONNECTOR_FULL_TYPE
    obj_type = td.fullType()
    ctor = {
        CONNECTOR_FULL_TYPE.Void: DataFillVoid,
        CONNECTOR_FULL_TYPE.NumInt8: DataFillInt,
        CONNECTOR_FULL_TYPE.NumInt16: DataFillInt,
        CONNECTOR_FULL_TYPE.NumInt32: DataFillInt,
        CONNECTOR_FULL_TYPE.NumInt64: DataFillInt,
        CONNECTOR_FULL_TYPE.NumUInt8: DataFillInt,
        CONNECTOR_FULL_TYPE.NumUInt16: DataFillInt,
        CONNECTOR_FULL_TYPE.NumUInt32: DataFillInt,
        CONNECTOR_FULL_TYPE.NumUInt64: DataFillInt,
        CONNECTOR_FULL_TYPE.NumFloat32: DataFillFloat,
        CONNECTOR_FULL_TYPE.NumFloat64: DataFillFloat,
        CONNECTOR_FULL_TYPE.NumFloatExt: DataFillFloat,
        CONNECTOR_FULL_TYPE.NumComplex64: DataFillFloat,
        CONNECTOR_FULL_TYPE.NumComplex128: DataFillFloat,
        CONNECTOR_FULL_TYPE.NumComplexExt: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitUInt8: DataFillInt,
        CONNECTOR_FULL_TYPE.UnitUInt16: DataFillInt,
        CONNECTOR_FULL_TYPE.UnitUInt32: DataFillInt,
        CONNECTOR_FULL_TYPE.UnitFloat32: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitFloat64: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitFloatExt: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitComplex64: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitComplex128: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitComplexExt: DataFillFloat,
        CONNECTOR_FULL_TYPE.BooleanU16: DataFillBool,
        CONNECTOR_FULL_TYPE.Boolean: DataFillBool,
        CONNECTOR_FULL_TYPE.String: DataFillString,
        CONNECTOR_FULL_TYPE.Path: DataFillPath,
        CONNECTOR_FULL_TYPE.Picture: DataFillString,
        CONNECTOR_FULL_TYPE.CString: DataFillCString,
        CONNECTOR_FULL_TYPE.PasString: DataFillCString,
        CONNECTOR_FULL_TYPE.Tag: DataFillString,
        #CONNECTOR_FULL_TYPE.SubString: DataFillBlob,
        CONNECTOR_FULL_TYPE.Array: DataFillArray,
        CONNECTOR_FULL_TYPE.ArrayDataPtr: DataFillArrayDataPtr,
        #CONNECTOR_FULL_TYPE.SubArray: DataFillBlob,
        CONNECTOR_FULL_TYPE.ArrayInterfc: DataFillArray,
        CONNECTOR_FULL_TYPE.Cluster: DataFillCluster,
        CONNECTOR_FULL_TYPE.LVVariant: DataFillLVVariant,
        CONNECTOR_FULL_TYPE.MeasureData: DataFillMeasureData,
        CONNECTOR_FULL_TYPE.ComplexFixedPt: DataFillComplexFixedPt,
        CONNECTOR_FULL_TYPE.FixedPoint: DataFillFixedPoint,
        CONNECTOR_FULL_TYPE.Block: DataFillBlock,
        #CONNECTOR_FULL_TYPE.TypeBlock: DataFillSingleContainer,
        CONNECTOR_FULL_TYPE.VoidBlock: DataFillVoid,
        CONNECTOR_FULL_TYPE.AlignedBlock: DataFillBlock,
        CONNECTOR_FULL_TYPE.RepeatedBlock: DataFillRepeatedBlock,
        CONNECTOR_FULL_TYPE.AlignmntMarker: DataFillVoid,
        #CONNECTOR_FULL_TYPE.Ptr: DataFillNumberPtr,
        #CONNECTOR_FULL_TYPE.PtrTo: DataFillSingleContainer,
        #CONNECTOR_FULL_TYPE.Function: DataFillFunction,
        #CONNECTOR_FULL_TYPE.TypeDef: DataFillTypeDef,
        #CONNECTOR_FULL_TYPE.PolyVI: DataFillBlob,
    }.get(obj_type, None)
    if ctor is None:
        ctor = DataFillAll
    return ctor(vi, idx, tm_flags, td, po)
