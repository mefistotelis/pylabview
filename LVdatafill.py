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
import LVxml as ET
import LVclasses
import LVconnector
import LVconnectorref


class DataFill:
    def __init__(self, vi, tdType, tdSubType, po):
        """ Creates new DataFill object, capable of handling generic data.
        """
        self.vi = vi
        self.po = po
        self.tdType = tdType
        self.tdSubType = tdSubType
        self.index = -1
        self.tm_flags = None
        self.td = None
        self.value = None

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


    def setTD(self, td, idx, tm_flags = 0):
        self.index = idx
        self.td = td
        self.tm_flags = tm_flags

    def initWithRSRC(self, bldata):
        self.initWithRSRCParse(bldata)
        if (self.po.verbose > 2):
            print("{:s}: {} offs after {}"\
              .format(self.vi.src_fname,str(self),bldata.tell()))
        pass

    def prepareDict(self):
        typeName = enumOrIntToName(self.tdType)
        return { 'type': typeName, 'value': self.value }

    def __repr__(self):
        d = self.prepareDict()
        from pprint import pformat
        return type(self).__name__ + pformat(d, indent=0, compact=True, width=512)

    def getXMLTagName(self):
        from LVconnector import CONNECTOR_FULL_TYPE, tdEnToName, mdFlavorEnToName
        from LVconnectorref import refnumEnToName
        if self.tdType == CONNECTOR_FULL_TYPE.MeasureData:
            tagName = mdFlavorEnToName(self.tdSubType)
        elif self.tdType == CONNECTOR_FULL_TYPE.Refnum:
            tagName = refnumEnToName(self.tdSubType)
        else:
            tagName = tdEnToName(self.tdType)
        return tagName

    def initWithXML(self, df_elem):
        """ Early part of Data Fill loading from XML file

        At the point it is executed, other sections are inaccessible.
        To be overriden by child classes which want to load more properties from XML.
        """
        pass

    def initWithXMLLate(self):
        """ Late part of Data Fill loading from XML file

        Can access some basic data from other blocks and sections.
        Useful only if properties needs an update after other blocks are accessible.
        """
        pass

    def exportXML(self, df_elem, fname_base):
        #self.parseData() # no need, as we never store default fill in raw form
        pass


class DataFillVoid(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = None

    def initWithXML(self, df_elem):
        pass

    def exportXML(self, df_elem, fname_base):
        pass


class DataFillInt(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.base = 10
        from LVconnector import CONNECTOR_FULL_TYPE
        if self.tdType in (CONNECTOR_FULL_TYPE.NumInt8,):
            self.size = 1
            self.signed = True
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumInt16,):
            self.size = 2
            self.signed = True
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumInt32,):
            self.size = 4
            self.signed = True
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumInt64,):
            self.size = 8
            self.signed = True
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumUInt8,):
            self.size = 1
            self.signed = False
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumUInt16,):
            self.size = 2
            self.signed = False
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumUInt32,):
            self.size = 4
            self.signed = False
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumUInt64,):
            self.size = 8
            self.signed = False
        elif self.tdType in (CONNECTOR_FULL_TYPE.UnitUInt8,):
            self.size = 1
            self.signed = False
        elif self.tdType in (CONNECTOR_FULL_TYPE.UnitUInt16,):
            self.size = 2
            self.signed = False
        elif self.tdType in (CONNECTOR_FULL_TYPE.UnitUInt32,):
            self.size = 4
            self.signed = False
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))

    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(self.size), byteorder='big', signed=self.signed)

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillFloat(DataFill):
    def initWithRSRCParse(self, bldata):
        from LVconnector import CONNECTOR_FULL_TYPE
        if self.tdType in (CONNECTOR_FULL_TYPE.NumFloat32,CONNECTOR_FULL_TYPE.UnitFloat32,):
            self.value = struct.unpack('>f', bldata.read(4))[0]
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumFloat64,CONNECTOR_FULL_TYPE.UnitFloat64,):
            self.value = struct.unpack('>d', bldata.read(8))[0]
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumFloatExt,CONNECTOR_FULL_TYPE.UnitFloatExt,):
            self.value = readQuadFloat(bldata)
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))

    def initWithXML(self, df_elem):
        self.value = float(df_elem.text)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:g}".format(self.value)
        pass


class DataFillComplex(DataFill):
    def initWithRSRCParse(self, bldata):
        from LVconnector import CONNECTOR_FULL_TYPE
        if self.tdType in (CONNECTOR_FULL_TYPE.NumComplex64,CONNECTOR_FULL_TYPE.UnitComplex64,):
            self.value = struct.unpack('>ff', bldata.read(8))
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumComplex128,CONNECTOR_FULL_TYPE.UnitComplex128,):
            self.value = struct.unpack('>dd', bldata.read(16))
        elif self.tdType in (CONNECTOR_FULL_TYPE.NumComplexExt,CONNECTOR_FULL_TYPE.UnitComplexExt,):
            self.value = (readQuadFloat(bldata),readQuadFloat(bldata),)
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))

    def initWithXML(self, df_elem):
        valRe = float(df_elem.find('real').text)
        valIm = float(df_elem.find('imag').text)
        self.value = (valRe,valIm,)
        pass

    def exportXML(self, df_elem, fname_base):
        tags = ('real', 'imag',)
        for i, val in enumerate(self.value):
            subelem = ET.SubElement(df_elem, tags[i])
            subelem.text = "{:g}".format(val)
        pass


class DataFillBool(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        from LVconnector import CONNECTOR_FULL_TYPE
        if self.tdType in (CONNECTOR_FULL_TYPE.BooleanU16,):
            self.size = 2
        elif self.tdType in (CONNECTOR_FULL_TYPE.Boolean,):
            ver = self.vi.getFileVersion()
            if isGreaterOrEqVersion(ver, 4,5,0):
                self.size = 1
            else:
                self.size = 2
        else:
            raise RuntimeError("Class {} used for unexpected type {}"\
              .format(type(self).__name__, self.getXMLTagName()))

    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(self.size), byteorder='big', signed=False)

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = str(self.value)
        pass


class DataFillString(DataFill):
    def initWithRSRCParse(self, bldata):
        strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        #if self.td.prop1 != 0xffffffff: # in such case part of the value might be irrelevant, as only
        # part to the size (self.td.prop1 & 0x7fffffff) is used; but the length stored is still valid
        self.value = bldata.read(strlen)

    def exportXML(self, df_elem, fname_base):
        elemText = self.value.decode(self.vi.textEncoding)
        ET.safe_store_element_text(df_elem, elemText)
        pass


class DataFillPath(DataFill):
    def initWithRSRCParse(self, bldata):
        startPos = bldata.tell()
        clsident = bldata.read(4)
        if clsident == b'PTH0':
            self.value = LVclasses.LVPath0(self.vi, self.po)
        elif clsident in (b'PTH1', b'PTH2',):
            self.value = LVclasses.LVPath1(self.vi, self.po)
        else:
            raise RuntimeError("Data fill {} contains path data of unrecognized class {}"\
              .format(self.getXMLTagName(),clsident))
        bldata.seek(startPos)
        self.value.parseRSRCData(bldata)

    def initWithXML(self, df_elem):
        for subelem in df_elem:
            clsident = subelem.tag
            if clsident == b'PTH0':
                self.value = LVclasses.LVPath0(self.vi, self.po)
            elif clsident in (b'PTH1', b'PTH2',):
                self.value = LVclasses.LVPath1(self.vi, self.po)
            else:
                raise RuntimeError("Data fill {} contains path data of unrecognized class {}"\
              .format(self.getXMLTagName(),clsident))
        self.value.initWithXML(subelem)
        pass

    def exportXML(self, df_elem, fname_base):
        self.value.exportXML(df_elem, fname_base)
        pass


class DataFillCString(DataFill):
    def initWithRSRCParse(self, bldata):
        # No idea why sonething which looks like string type stores 32-bit value instead
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillArray(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.dimensions = []

    def prepareDict(self):
        d = super().prepareDict()
        d.update( { 'dimensions': self.dimensions } )
        return d

    def initWithRSRCParse(self, bldata):
        self.dimensions = []
        for dim in self.td.dimensions:
            val = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.dimensions.append(val)
        # Multiply sizes of each dimension to get total number of items
        totItems = 1
        # TODO the amounts are in self.dimensions; maybe they need to be same as self.td.dimensions, unless dynamic size is used? print warning?
        for dim in self.dimensions:
            totItems *= dim & 0x7fffffff
        self.value = []
        if self.td.clients[0].index >= 0:
            VCTP = self.vi.get_or_raise('VCTP')
            sub_td = VCTP.getFlatType(self.td.clients[0].index)
        else:
            sub_td = self.td.clients[0].nested
        #if sub_td.fullType() in (CONNECTOR_FULL_TYPE.Boolean,) and isSmallerVersion(ver, 4,5,0,1): # TODO expecting special case, never seen it though
        if totItems > self.po.array_data_limit:
                raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
                  .format(self.getXMLTagName(), totItems, self.po.array_data_limit))
        for i in range(totItems):
            try:
                sub_df = newDataFillObjectWithTD(self.vi, self.td.clients[0].index, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(sub_td.fullType()), str(e)))
        pass

    def initWithXML(self, df_elem):
        self.dimensions = []
        self.value = []
        for i, subelem in enumerate(df_elem):
            if (subelem.tag == 'dim'):
                val = int(df_elem.text, 0)
                self.dimensions.append(val)
                continue
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def exportXML(self, df_elem, fname_base):
        for i, dim in enumerate(self.dimensions):
            subelem = ET.SubElement(df_elem, 'dim')
            subelem.text = "{:d}".format(dim)
        for i, sub_df in enumerate(self.value):
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class DataFillArrayDataPtr(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillCluster(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = []
        for cli_idx, conn_idx, sub_td, conn_flags in self.td.clientsEnumerate():
            try:
                sub_df = newDataFillObjectWithTD(self.vi, conn_idx, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(sub_td.fullType()), str(e)))
        pass

    def initWithXML(self, df_elem):
        self.value = []
        for i, subelem in enumerate(df_elem):
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def exportXML(self, df_elem, fname_base):
        for i, sub_df in enumerate(self.value):
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class DataFillLVVariant(DataFill):
    def initWithRSRCParse(self, bldata):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 6,0,0,2):
            self.value = LVclasses.LVVariant(0, self.vi, self.po, useConsolidatedTypes=True, allowFillValue=True)
        else:
            self.value = LVclasses.OleVariant(0, self.vi, self.po)
        self.value.parseRSRCData(bldata)

    def initWithXML(self, df_elem):
        if df_elem.tag == LVclasses.LVVariant.__name__:
            self.value = LVclasses.LVVariant(0, self.vi, self.po, useConsolidatedTypes=True, allowFillValue=True)
        elif df_elem.tag == LVclasses.OleVariant.__name__:
            self.value = LVclasses.OleVariant(0, self.vi, self.po)
        else:
            raise AttributeError("Class {} encountered unexpected tag '{}'".format(type(self).__name__, df_elem.tag))
        self.value.initWithXML(df_elem)
        pass

    def exportXML(self, df_elem, fname_base):
        self.value.exportXML(df_elem, fname_base)
        pass


class DataFillMeasureData(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        ver = self.vi.getFileVersion()
        from LVconnector import MEASURE_DATA_FLAVOR, CONNECTOR_FULL_TYPE, newConnectorObject,\
          newDigitalTableCluster, newDigitalWaveformCluster, newDynamicTableCluster,\
          newAnalogWaveformCluster, newOldFloat64WaveformCluster

        if isSmallerVersion(ver, 7,0,0,2):
            raise NotImplementedError("MeasureData {} default value read is not implemented for versions below LV7"\
              .format(enumOrIntToName(sub_td.dtFlavor())))

        if self.tdSubType in (MEASURE_DATA_FLAVOR.OldFloat64Waveform,):
            self.containedTd = newOldFloat64WaveformCluster(self.vi, -1, 0, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Int16Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumInt16, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Float64Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumFloat64, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Float32Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumFloat32, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.TimeStamp,):
            # Use block of 16 bytes as Timestamp
            self.containedTd = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.Block, self.po)
            self.containedTd.blkSize = 16
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Digitaldata,):
            self.containedTd = newDigitalTableCluster(self.vi, -1, 0, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.DigitalWaveform,):
            self.containedTd = newDigitalWaveformCluster(self.vi, -1, 0, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Dynamicdata,):
            self.containedTd = newDynamicTableCluster(self.vi, -1, 0, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.FloatExtWaveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumFloatExt, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.UInt8Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumUInt8, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.UInt16Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumUInt16, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.UInt32Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumUInt32, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Int8Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumInt8, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Int32Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumInt32, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Complex64Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumComplex64, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Complex128Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumComplex128, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.ComplexExtWaveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumComplexExt, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.Int64Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumInt64, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        elif self.tdSubType in (MEASURE_DATA_FLAVOR.UInt64Waveform,):
            tdInner = newConnectorObject(self.vi, -1, 0, CONNECTOR_FULL_TYPE.NumUInt64, self.po)
            self.containedTd = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
        else:
            raise NotImplementedError("MeasureData {} default value read failed due to unsupported flavor"\
              .format(self.getXMLTagName()))

    def prepareDict(self):
        flavorName = enumOrIntToName(self.tdSubType)
        d = super().prepareDict()
        d.update( { 'flavor': flavorName } )
        return d

    def initWithRSRCParse(self, bldata):
        self.value = []
        try:
            sub_df = newDataFillObjectWithTD(self.vi, -1, self.tm_flags, self.containedTd, self.po)
            self.value.append(sub_df)
            sub_df.initWithRSRC(bldata)
        except Exception as e:
            raise RuntimeError("MeasureData flavor {}: {}"\
              .format(enumOrIntToName(self.containedTd.fullType()), str(e)))
        pass

    def initWithXML(self, df_elem):
        self.value = []
        for i, subelem in enumerate(df_elem):
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def exportXML(self, df_elem, fname_base):
        for i, sub_df in enumerate(self.value):
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class DataFillComplexFixedPt(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.value = 2 * [None]
        self.vflags = 2 * [None]

    def prepareDict(self):
        d = super().prepareDict()
        d.update( { 'vflags': self.vflags } )
        return d

    def initWithRSRCParse(self, bldata):
        # Not sure about the order of values in this type
        self.value = 2 * [None]
        self.vflags = 2 * [None]
        for i in range(2):
            self.value[i] = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
            if self.td.allocOv:
                self.vflags[i] = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        pass

    def initWithXML(self, df_elem):
        subelem = df_elem.find('real')
        valRe = int(subelem.text, 0)
        flagRe = subelem.get("Flags")
        if flagRe is not None:
            flagRe = int(flagRe, 0)
        subelem = df_elem.find('imag')
        valIm = int(subelem.text, 0)
        flagIm = subelem.get("Flags")
        if flagIm is not None:
            flagIm = int(flagIm, 0)
        self.value = [valRe,valIm,]
        self.vflags = [flagRe,flagIm,]
        pass

    def exportXML(self, df_elem, fname_base):
        tags = ("real", "imag",)
        for i, val in enumerate(self.value):
            subelem = ET.SubElement(df_elem, tags[i])
            subelem.text = "{:d}".format(val)
            subelem.set("Flags", "0x{:02X}".format(self.vflags[i]))
        pass


class DataFillFixedPoint(DataFill):
    def __init__(self, *args):
        super().__init__(*args)
        self.vflags = None

    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
        if self.td.allocOv:
            self.vflags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        else:
            self.vflags = None

    def initWithXML(self, df_elem):
        valRe = int(df_elem.text, 0)
        flagRe = df_elem.get("Flags")
        if flagRe is not None:
            flagRe = int(flagRe, 0)
        self.value = valRe
        self.vflags = flagRe
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        if self.vflags is not None:
            df_elem.set("Flags", "0x{:02X}".format(self.vflags))
        pass


class DataFillBlock(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = bldata.read(self.td.blkSize)

    def initWithXML(self, df_elem):
        self.value = bytes.fromhex(df_elem.text)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = self.value.hex()
        pass


class DataFillRepeatedBlock(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = []
        VCTP = self.vi.get_or_raise('VCTP')
        sub_td = VCTP.getFlatType(self.td.typeFlatIdx)
        if self.td.numRepeats > self.po.array_data_limit:
            raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
              .format(self.getXMLTagName(), self.td.numRepeats, self.po.array_data_limit))
        for i in range(self.td.numRepeats):
            try:
                sub_df = newDataFillObjectWithTD(self.vi, self.td.typeFlatIdx, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(sub_td.fullType()), str(e)))
        pass

    def initWithXML(self, df_elem):
        self.value = []
        for i, subelem in enumerate(df_elem):
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def exportXML(self, df_elem, fname_base):
        for i, sub_df in enumerate(self.value):
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class DataFillSimpleRefnum(DataFill):
    """ Data Fill for Simple Refnum types.

    Used for "normal" ref types, which only contain 4 byte value.
    """
    def initWithRSRCParse(self, bldata):
        # The format seem to be different for LV6.0.0 and older, but still 4 bytes
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillIORefnum(DataFill):
    """ Data Fill for IORefnum types.

    Used for ref types which represent IORefnum.
    """
    def initWithRSRCParse(self, bldata):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 6,0,0):
            if self.isRefnumTag(self.td):
                strlen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.value = bldata.read(strlen)
            else:
                self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        else:
            self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def initWithXML(self, df_elem):
        storedAs = df_elem.get("StoredAs")
        if storedAs == "String":
            self.value = df_elem.text.encode(self.vi.textEncoding)
        elif storedAs == "Int":
            self.value = int(df_elem.text, 0)
        else:
            raise AttributeError("Class {} encountered unexpected StoredAs value '{}'".format(type(self).__name__, storedAs))
        pass

    def exportXML(self, df_elem, fname_base):
        if isinstance(self.value, (bytes, bytearray,)):
            elemText = self.value.decode(self.vi.textEncoding)
            ET.safe_store_element_text(df_elem, elemText)
            df_elem.set("StoredAs", "String")
        else:
            df_elem.text = "{:d}".format(self.value)
            df_elem.set("StoredAs", "Int")
        pass


class DataFillUDRefnum(DataFill):
    """ Data Fill for non-tag UDRefnum types.

    Used for ref types which represent Non-tag subtypes of UDRefnum.
    """
    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillUDTagRefnum(DataFill):
    """ Data Fill for tag UDRefnum types.

    Used for ref types which represent Tag subtypes of UDRefnum.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.usrdef1 = None
        self.usrdef2 = None
        self.usrdef3 = None
        self.usrdef4 = None

    def prepareDict(self):
        d = super().prepareDict()
        d.update( { 'usrdef1': self.usrdef1, 'usrdef2': self.usrdef2, 'usrdef3': self.usrdef3, 'usrdef4': self.usrdef4 } )
        return d

    def initWithRSRCParse(self, bldata):
        from LVconnectorref import REFNUM_TYPE
        ver = self.vi.getFileVersion()
        self.usrdef1 = None
        self.usrdef2 = None
        self.usrdef3 = None
        self.usrdef4 = None
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

    def initWithXML(self, df_elem):
        self.usrdef1 = None
        self.usrdef2 = None
        self.usrdef3 = None
        self.usrdef4 = None
        self.value = df_elem.text.encode(self.vi.textEncoding)
        usrdef = df_elem.get("UsrDef1")
        if usrdef is not None:
            self.usrdef1 = usrdef.encode(self.vi.textEncoding)
        usrdef = df_elem.get("UsrDef2")
        if usrdef is not None:
            self.usrdef2 = usrdef.encode(self.vi.textEncoding)
        usrdef = df_elem.get("UsrDef3")
        if usrdef is not None:
            self.usrdef3 = int(usrdef, 0)
        usrdef = df_elem.get("UsrDef4")
        if usrdef is not None:
            self.usrdef4 = usrdef.encode(self.vi.textEncoding)
        pass

    def exportXML(self, df_elem, fname_base):
        elemText = self.value.decode(self.vi.textEncoding)
        ET.safe_store_element_text(df_elem, elemText)
        if self.usrdef1 is not None:
            df_elem.set("UsrDef1", self.usrdef1.decode(self.vi.textEncoding))
        if self.usrdef2 is not None:
            df_elem.set("UsrDef2", self.usrdef2.decode(self.vi.textEncoding))
        if self.usrdef3 is not None:
            df_elem.set("UsrDef3", "{:d}".format(self.usrdef3))
        if self.usrdef4 is not None:
            df_elem.set("UsrDef4", self.usrdef4.decode(self.vi.textEncoding))
        pass


class DataFillUDClassInst(DataFill):
    """ Data Fill for UDClassInst Refnum types.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.value = []
        self.libName = b''

    def initWithRSRCParse(self, bldata):
        self.value = []
        numLevels = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.libName = bldata.read(strlen)
        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes
        if numLevels > self.po.connector_list_limit:
            raise RuntimeError("Data type {} claims to contain {} fields, expected below {}"\
              .format(self.getXMLTagName(), numLevels, self.po.connector_list_limit))
        for i in range(numLevels):
            datalen = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            libVersion = bldata.read(datalen)
            self.value.append(libVersion)

    def initWithXML(self, df_elem):
        self.value = []
        self.libName = b''
        for i, subelem in enumerate(df_elem):
            if subelem.tag == "LibName":
                self.libName = subelem.text.encode(self.vi.textEncoding)
            elif subelem.tag == "LibVersion":
                val = subelem.text.encode(self.vi.textEncoding)
                self.value.append(val)
            else:
                raise AttributeError("Class {} encountered unexpected tag '{}'".format(type(self).__name__, subelem.tag))
        pass

    def exportXML(self, df_elem, fname_base):
        if True:
            subelem = ET.SubElement(df_elem, "LibName")
            elemText = self.libName.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, elemText)
        for i, libVersion in enumerate(self.value):
            subelem = ET.SubElement(df_elem, "LibVersion")
            elemText = libVersion.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, elemText)
        pass


class DataFillPtr(DataFill):
    def initWithRSRCParse(self, bldata):
        ver = self.vi.getFileVersion()
        if isSmallerVersion(ver, 8,6,0,1):
            self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        else:
            self.value = None

    def initWithXML(self, df_elem):
        if df_elem.text != "None":
            self.value = int(df_elem.text, 0)
        else:
            self.value = None
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{}".format(self.value)
        pass


class DataFillPtrTo(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

    def initWithXML(self, df_elem):
        self.value = int(df_elem.text, 0)
        pass

    def exportXML(self, df_elem, fname_base):
        df_elem.text = "{:d}".format(self.value)
        pass


class DataFillExtData(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = None # TODO implement reading ExtData
        raise NotImplementedError("ExtData default value read is not implemented")

    def initWithXML(self, df_elem):
        raise NotImplementedError("ExtData default value read is not implemented")


class DataFillUnexpected(DataFill):
    """ Data fill for types for which we never expect this call, but it may be ignored

    Types which reference this class would cause silently ignored error in LV14.
    """
    def initWithRSRCParse(self, bldata):
        self.value = None
        eprint("{:s}: Warning: Data fill asks to read default value of {} type, this should never happen."\
          .format(self.vi.src_fname, self.getXMLTagName()))

    def initWithXML(self, df_elem):
        self.value = None
        eprint("{:s}: Warning: Data fill parsing found default value of {} type, this should never happen."\
          .format(self.vi.src_fname, self.getXMLTagName()))
        pass

    def exportXML(self, df_elem, fname_base):
        pass


class DataFillTypeDef(DataFill):
    def initWithRSRCParse(self, bldata):
        self.value = []
        # We expect only one client within TypeDef
        for client in self.td.clients:
            try:
                sub_df = newDataFillObjectWithTD(self.vi, -1, self.tm_flags, client.nested, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(client.nested.fullType()), str(e)))
        pass

    def initWithXML(self, df_elem):
        self.value = []
        for i, subelem in enumerate(df_elem):
            sub_df = newDataFillObjectWithTag(self.vi, subelem.tag, self.po)
            sub_df.initWithXML(subelem)
            self.value.append(sub_df)
        pass

    def exportXML(self, df_elem, fname_base):
        for i, sub_df in enumerate(self.value):
            subelem = ET.SubElement(df_elem, sub_df.getXMLTagName())
            sub_df.exportXML(subelem, fname_base)
        pass


class SpecialDSTMCluster(DataFillCluster):
    def initWithRSRCParse(self, bldata):
        self.value = []
        skipNextEntry = ((self.tm_flags & 0x0200) != 0)
        for cli_idx, conn_idx, sub_td, conn_flags in self.td.clientsEnumerate():
            if not self.isSpecialDSTMClusterElement(cli_idx, self.tm_flags):
                continue
            if skipNextEntry:
                skipNextEntry = False
                continue
            try:
                sub_df = newDataFillObjectWithTD(self.vi, conn_idx, self.tm_flags, sub_td, self.po)
                self.value.append(sub_df)
                sub_df.initWithRSRC(bldata)
            except Exception as e:
                raise RuntimeError("Data type {}: {}".format(enumOrIntToName(sub_td.fullType()), str(e)))
            pass
        pass


def newSpecialDSTMClusterWithTD(vi, idx, tm_flags, td, po):
    """ Creates and returns new data fill object with given parameters
    """
    from LVconnector import CONNECTOR_FULL_TYPE
    tdType = td.fullType()
    tdSubType = None
    df = SpecialDSTMCluster(vi, tdType, tdSubType, po)
    df.setTD(td, idx, tm_flags)
    return df

def newDataFillRefnum(vi, tdType, tdSubType, po):
    """ Creates and returns new data fill object for refnum with given parameters
    """
    from LVconnectorref import REFNUM_TYPE
    refType = tdSubType
    ctor = {
        REFNUM_TYPE.IVIRef: DataFillIORefnum,
        REFNUM_TYPE.VisaRef: DataFillIORefnum,
        REFNUM_TYPE.Imaq: DataFillIORefnum,
        REFNUM_TYPE.UsrDefTagFlt: DataFillUDTagRefnum,
        REFNUM_TYPE.UsrDefndTag: DataFillUDTagRefnum,
        REFNUM_TYPE.UsrDefined: DataFillUDRefnum,
        REFNUM_TYPE.UDClassInst: DataFillUDClassInst,
    }.get(refType, DataFillSimpleRefnum)
    if ctor is None:
        raise RuntimeError("Data type Refnum kind {}: No known way to read default data"\
          .format(enumOrIntToName(refType),str(e)))
    return ctor(vi, tdType, tdSubType, po)


def newDataFillObject(vi, tdType, tdSubType, po):
    """ Creates and returns new data fill object with given parameters
    """
    from LVconnector import CONNECTOR_FULL_TYPE
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
        CONNECTOR_FULL_TYPE.NumComplex64: DataFillComplex,
        CONNECTOR_FULL_TYPE.NumComplex128: DataFillComplex,
        CONNECTOR_FULL_TYPE.NumComplexExt: DataFillComplex,
        CONNECTOR_FULL_TYPE.UnitUInt8: DataFillInt,
        CONNECTOR_FULL_TYPE.UnitUInt16: DataFillInt,
        CONNECTOR_FULL_TYPE.UnitUInt32: DataFillInt,
        CONNECTOR_FULL_TYPE.UnitFloat32: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitFloat64: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitFloatExt: DataFillFloat,
        CONNECTOR_FULL_TYPE.UnitComplex64: DataFillComplex,
        CONNECTOR_FULL_TYPE.UnitComplex128: DataFillComplex,
        CONNECTOR_FULL_TYPE.UnitComplexExt: DataFillComplex,
        CONNECTOR_FULL_TYPE.BooleanU16: DataFillBool,
        CONNECTOR_FULL_TYPE.Boolean: DataFillBool,
        CONNECTOR_FULL_TYPE.String: DataFillString,
        CONNECTOR_FULL_TYPE.Path: DataFillPath,
        CONNECTOR_FULL_TYPE.Picture: DataFillString,
        CONNECTOR_FULL_TYPE.CString: DataFillCString,
        CONNECTOR_FULL_TYPE.PasString: DataFillCString,
        CONNECTOR_FULL_TYPE.Tag: DataFillString,
        CONNECTOR_FULL_TYPE.SubString: DataFillUnexpected,
        CONNECTOR_FULL_TYPE.Array: DataFillArray,
        CONNECTOR_FULL_TYPE.ArrayDataPtr: DataFillArrayDataPtr,
        CONNECTOR_FULL_TYPE.SubArray: DataFillUnexpected,
        CONNECTOR_FULL_TYPE.ArrayInterfc: DataFillArray,
        CONNECTOR_FULL_TYPE.Cluster: DataFillCluster,
        CONNECTOR_FULL_TYPE.LVVariant: DataFillLVVariant,
        CONNECTOR_FULL_TYPE.MeasureData: DataFillMeasureData,
        CONNECTOR_FULL_TYPE.ComplexFixedPt: DataFillComplexFixedPt,
        CONNECTOR_FULL_TYPE.FixedPoint: DataFillFixedPoint,
        CONNECTOR_FULL_TYPE.Block: DataFillBlock,
        CONNECTOR_FULL_TYPE.TypeBlock: DataFillTypeDef,
        CONNECTOR_FULL_TYPE.VoidBlock: DataFillVoid,
        CONNECTOR_FULL_TYPE.AlignedBlock: DataFillBlock,
        CONNECTOR_FULL_TYPE.RepeatedBlock: DataFillRepeatedBlock,
        CONNECTOR_FULL_TYPE.AlignmntMarker: DataFillVoid,
        CONNECTOR_FULL_TYPE.Refnum: newDataFillRefnum,
        CONNECTOR_FULL_TYPE.Ptr: DataFillPtr,
        CONNECTOR_FULL_TYPE.PtrTo: DataFillPtrTo,
        CONNECTOR_FULL_TYPE.ExtData: DataFillExtData,
        CONNECTOR_FULL_TYPE.Function: DataFillUnexpected,
        CONNECTOR_FULL_TYPE.TypeDef: DataFillTypeDef,
        CONNECTOR_FULL_TYPE.PolyVI: DataFillUnexpected,
    }.get(tdType, None)
    if ctor is None:
        raise RuntimeError("Data type {}: No known way to read default data"\
          .format(enumOrIntToName(tdType),str(e)))
    return ctor(vi, tdType, tdSubType, po)

def newDataFillObjectWithTD(vi, idx, tm_flags, td, po):
    """ Creates and returns new data fill object with given parameters
    """
    from LVconnector import CONNECTOR_FULL_TYPE
    tdType = td.fullType()
    if tdType == CONNECTOR_FULL_TYPE.MeasureData:
        tdSubType = td.dtFlavor()
    elif tdType == CONNECTOR_FULL_TYPE.Refnum:
        tdSubType = td.refType()
    else:
        tdSubType = None
    df = newDataFillObject(vi, tdType, tdSubType, po)
    df.setTD(td, idx, tm_flags)
    return df

def newDataFillObjectWithTag(vi, tagName, po):
    """ Creates and returns new data fill object from given XML tag name
    """
    from LVconnector import CONNECTOR_FULL_TYPE, tdNameToEnum, mdFlavorNameToEnum
    from LVconnectorref import refnumNameToEnum
    tdType = tdNameToEnum(tagName)
    if tdType is None:
        raise AttributeError("Data Fill creation encountered unexpected tag '{}'".format(tagName))
    if tdType == CONNECTOR_FULL_TYPE.MeasureData:
        tdSubType = LVconnector.mdFlavorNameToEnum(subelem.tag)
    elif tdType == CONNECTOR_FULL_TYPE.Refnum:
        tdSubType = refnumNameToEnum(subelem.tag)
    else:
        tdSubType = None
    df = newDataFillObject(vi, tdType, tdSubType, po)
    return df
