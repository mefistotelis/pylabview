# -*- coding: utf-8 -*-

""" LabView RSRC file format Link Object Refs.

    Support of Link Identities storage.
"""

# Copyright (C) 2019-2020 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.


import enum

from hashlib import md5
from io import BytesIO
from types import SimpleNamespace
from ctypes import *

from LVmisc import *
import LVxml as ET
import LVclasses
import LVheap
import LVdatatype
import LVdatafill


class LinkObjBase:
    """ Generic base for LinkObject Identities.

    Provides methods to be overriden in inheriting classes.
    """
    def __init__(self, vi, blockref, list_ident, ident, po):
        """ Creates new link object.
        """
        self.vi = vi
        self.blockref = blockref
        self.po = po
        self.ident = ident
        self.list_ident = list_ident
        self.content = None
        if self.__doc__:
            self.full_name = " {:s} ".format(self.__doc__.split('\n')[0].strip())
        else:
            self.full_name = ""

    def parseBool(self, bldata):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 4,5,0,1):
            bool_sz = 1
        else:
            bool_sz = 2
        return int.from_bytes(bldata.read(bool_sz), byteorder='big', signed=False)

    def prepareBool(self, val):
        ver = self.vi.getFileVersion()
        if isGreaterOrEqVersion(ver, 4,5,0,1):
            bool_sz = 1
        else:
            bool_sz = 2
        data_buf = b''
        data_buf += int(val).to_bytes(bool_sz, byteorder='big', signed=False)
        return data_buf

    def parsePathRef(self, bldata):
        start_pos = bldata.tell()
        clsident = bldata.read(4)
        if clsident == b'PTH0':
            pathRef = LVclasses.LVPath0(self.vi, self.blockref, self.po)
        elif clsident in (b'PTH1', b'PTH2',):
            pathRef = LVclasses.LVPath1(self.vi, self.blockref, self.po)
        else:
            raise RuntimeError("{:s} {} contains path data of unrecognized class {}"\
          .format(type(self).__name__,self.ident,clsident))
        bldata.seek(start_pos)
        pathRef.parseRSRCData(bldata)
        return pathRef

    def initWithXMLPathRef(self, pr_elem):
        clsident = b''
        clsident_str = pr_elem.get("Ident")
        if clsident_str is not None:
            clsident = getRsrcTypeFromPrettyStr(clsident_str)
        if clsident == b'PTH0':
            pathRef = LVclasses.LVPath0(self.vi, self.blockref, self.po)
        elif clsident in (b'PTH1', b'PTH2',):
            pathRef = LVclasses.LVPath1(self.vi, self.blockref, self.po)
        else:
            raise RuntimeError("{:s} {} contains path data of unrecognized class {}"\
          .format(type(self).__name__,self.ident,clsident))

        pathRef.initWithXML(pr_elem)
        return pathRef

    def initWithXMLQualifiedName(self, items, qn_elem):
        for i, subelem in enumerate(qn_elem):
            if (subelem.tag == "String"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    items.append(elem_text.encode(self.vi.textEncoding))
                else:
                    items.append(b'')
            else:
                raise AttributeError("QualifiedName contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXMLQualifiedName(self, items, qn_elem):
        for i, name in enumerate(items):
            subelem = ET.SubElement(qn_elem,"String")

            name_text = name.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, name_text)
        pass

    def clearBasicLinkSaveInfo(self):
        self.linkSaveQualName = []
        self.linkSavePathRef = None
        self.linkSaveFlag = 0

    def parseBasicLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearBasicLinkSaveInfo()

        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes

        start_pos = bldata.tell()
        self.linkSaveQualName = readQualifiedName(bldata, self.po)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "BasicLinkSaveInfo.QualName")

        if (bldata.tell() % 2) > 0:
            bldata.read(2 - (bldata.tell() % 2)) # Padding bytes

        start_pos = bldata.tell()
        self.linkSavePathRef = self.parsePathRef(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "BasicLinkSaveInfo.PathRef")

        if isGreaterOrEqVersion(ver, 8,5,0,1):
            if isGreaterOrEqVersion(ver, 8,6,0,1):
                self.linkSaveFlag = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.appendPrintMapEntry(bldata.tell(), 4, 1, "BasicLinkSaveInfo.Flag")
            else:
                self.linkSaveFlag = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                self.appendPrintMapEntry(bldata.tell(), 1, 1, "BasicLinkSaveInfo.Flag")
        pass

    def prepareBasicLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''
        if (start_offs+len(data_buf)) % 4 > 0:
            padding_len = 4 - ((start_offs+len(data_buf)) % 4)
            data_buf += (b'\0' * padding_len)

        data_buf += prepareQualifiedName(self.linkSaveQualName, self.po)

        if (start_offs+len(data_buf)) % 2 > 0:
            padding_len = 2 - ((start_offs+len(data_buf)) % 2)
            data_buf += (b'\0' * padding_len)

        data_buf += self.linkSavePathRef.prepareRSRCData()

        if isGreaterOrEqVersion(ver, 8,5,0,1):
            if isGreaterOrEqVersion(ver, 8,6,0,1):
                data_buf += int(self.linkSaveFlag).to_bytes(4, byteorder='big', signed=False)
            else:
                data_buf += int(self.linkSaveFlag).to_bytes(1, byteorder='big', signed=False)
        return data_buf

    def initWithXMLBasicLinkSaveInfo(self, lnkobj_elem):
        self.clearBasicLinkSaveInfo()

        linkSaveFlag = lnkobj_elem.get("LinkSaveFlag")
        if linkSaveFlag is not None:
            self.linkSaveFlag = int(linkSaveFlag, 0)

        for i, subelem in enumerate(lnkobj_elem):
            if (subelem.tag == "LinkSaveQualName"):
                self.initWithXMLQualifiedName(self.linkSaveQualName, subelem)
            elif (subelem.tag == "LinkSavePathRef"):
                self.linkSavePathRef = self.initWithXMLPathRef(subelem)
            else:
                pass # No exception here - parent may define more tags
        if self.linkSavePathRef is None:
            raise AttributeError("BasicLinkSaveInfo has no LinkSavePathRef in {}".format(self.ident))
        pass

    def exportXMLBasicLinkSaveInfo(self, lnkobj_elem, fname_base):
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        lnkobj_elem.tag = pretty_ident

        lnkobj_elem.set("LinkSaveFlag", "{:d}".format(self.linkSaveFlag))

        subelem = ET.SubElement(lnkobj_elem,"LinkSaveQualName")
        self.exportXMLQualifiedName(self.linkSaveQualName, subelem)

        subelem = ET.SubElement(lnkobj_elem,"LinkSavePathRef")
        self.linkSavePathRef.exportXML(subelem, fname_base)

    def clearVILinkRefInfo(self):
        self.viLinkFieldA = 0
        self.viLinkLibVersion = 0
        self.viLinkField4 = 0
        self.viLinkFieldB = b''
        self.viLinkFieldC = b''
        self.viLinkFieldD = 0

    def parseVILinkRefInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearVILinkRefInfo()

        flagBt = 0xff
        if isGreaterOrEqVersion(ver, 14,0,0,3):
            flagBt = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.appendPrintMapEntry(bldata.tell(), 1, 1, "VILinkRefInfo.FlagBt")
        if flagBt != 0xff:
            self.viLinkFieldA = flagBt & 1
            self.viLinkLibVersion = (flagBt >> 1) & 0x1F
            self.viLinkField4 = flagBt >> 6
        else:
            if isGreaterOrEqVersion(ver, 8,0,0,3):
                self.viLinkField4 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.appendPrintMapEntry(bldata.tell(), 4, 1, "VILinkRefInfo.Field4")
                self.viLinkLibVersion = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
                self.appendPrintMapEntry(bldata.tell(), 8, 1, "VILinkRefInfo.LibVersion")
            else:
                self.viLinkField4 = 1
                self.viLinkLibVersion = 0
            if isGreaterOrEqVersion(ver, 6,0,0,1):
                self.viLinkFieldB = bldata.read(4)
                self.appendPrintMapEntry(bldata.tell(), 4, 1, "VILinkRefInfo.FieldB")
                self.viLinkFieldC = bldata.read(4)
                self.appendPrintMapEntry(bldata.tell(), 4, 1, "VILinkRefInfo.FieldC")
                self.viLinkFieldD = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
                self.appendPrintMapEntry(bldata.tell(), 4, 1, "VILinkRefInfo.FieldD")
        pass

    def prepareVILinkRefInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        flagBt = 0xff
        if isGreaterOrEqVersion(ver, 14,0,0,3):
            if (self.viLinkFieldA <= 1) and (self.viLinkLibVersion <= 0x1F) and (self.viLinkField4 <= 0x3):
                flagBt = self.viLinkFieldA = (self.viLinkFieldA & 1)
                flagBt |= (self.viLinkLibVersion & 0x1F) << 1
                flagBt |= (self.viLinkField4 & 0x3) << 6
            data_buf += int(flagBt).to_bytes(1, byteorder='big', signed=False)

        if flagBt != 0xff:
            pass
        else:
            if isGreaterOrEqVersion(ver, 8,0,0,3):
                data_buf += int(self.viLinkField4).to_bytes(4, byteorder='big', signed=False)
                data_buf += int(self.viLinkLibVersion).to_bytes(8, byteorder='big', signed=False)
            if isGreaterOrEqVersion(ver, 6,0,0,1):
                data_buf += self.viLinkFieldB[:4]
                data_buf += self.viLinkFieldC[:4]
                data_buf += int(self.viLinkFieldD).to_bytes(4, byteorder='big', signed=True)
        return data_buf

    def initWithXMLVILinkRefInfo(self, lnkobj_elem):
        self.clearVILinkRefInfo()

        viLinkLibVersion = lnkobj_elem.get("VILinkLibVersion")
        if viLinkLibVersion is not None:
            self.viLinkLibVersion = int(viLinkLibVersion, 0)
        viLinkFieldA = lnkobj_elem.get("VILinkFieldA")
        if viLinkFieldA is not None:
            self.viLinkFieldA = int(viLinkFieldA, 0)
        viLinkField4 = lnkobj_elem.get("VILinkField4")
        if viLinkField4 is not None:
            self.viLinkField4 = int(viLinkField4, 0)

        viLinkFieldB = lnkobj_elem.get("VILinkFieldB")
        if viLinkFieldB is not None:
            self.viLinkFieldB = bytes.fromhex(viLinkFieldB)
        viLinkFieldC = lnkobj_elem.get("VILinkFieldC")
        if viLinkFieldC is not None:
            self.viLinkFieldC = bytes.fromhex(viLinkFieldC)
        viLinkFieldD = lnkobj_elem.get("VILinkFieldD")
        if viLinkFieldD is not None:
            self.viLinkFieldD = int(viLinkFieldD, 0)
        pass

    def exportXMLVILinkRefInfo(self, lnkobj_elem, fname_base):
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        lnkobj_elem.tag = pretty_ident

        lnkobj_elem.set("VILinkLibVersion", "{:d}".format(self.viLinkLibVersion))
        lnkobj_elem.set("VILinkFieldA", "{:d}".format(self.viLinkFieldA))
        lnkobj_elem.set("VILinkField4", "{:d}".format(self.viLinkField4))

        lnkobj_elem.set("VILinkFieldB", "{:s}".format(self.viLinkFieldB.hex()))
        lnkobj_elem.set("VILinkFieldC", "{:s}".format(self.viLinkFieldC.hex()))
        lnkobj_elem.set("VILinkFieldD", "{:d}".format(self.viLinkFieldD))

    def clearTypedLinkSaveInfo(self):
        self.clearBasicLinkSaveInfo()
        self.clearVILinkRefInfo()
        self.typedLinkFlags = 0
        self.typedLinkTD = None
        # Properties used only for LV7 and older
        self.typedLinkOffsetList = []

    def parseTypedLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearTypedLinkSaveInfo()

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            start_pos = bldata.tell()
            self.parseBasicLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "TypedLinkSaveInfo.BasicLinkSaveInfo")

            start_pos = bldata.tell()
            clientTD = SimpleNamespace()
            clientTD.index = readVariableSizeFieldU2p2(bldata)
            clientTD.flags = 0 # Only Type Mapped entries have it non-zero
            self.typedLinkTD = clientTD
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "TypedLinkSaveInfo.TD_TypeID")

            self.parseVILinkRefInfo(bldata)

            if isGreaterOrEqVersion(ver, 12,0,0,3):
                self.typedLinkFlags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.appendPrintMapEntry(bldata.tell(), 4, 1, "TypedLinkSaveInfo.Flags")
        else:
            # We cannot use parseBasicLinkSaveInfo(), but lets try keeping variables similar

            start_pos = bldata.tell()
            self.linkSaveQualName = [ readPStr(bldata, 2, self.po) ]
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "TypedLinkSaveInfo.QualName")

            start_pos = bldata.tell()
            self.typedLinkOffsetList = self.parseLinkOffsetList(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "TypedLinkSaveInfo.OffsetList")

            # TD was stored directly before consolidated list was introduced
            obj_pos = bldata.tell()
            obj_type, obj_flags, obj_len = LVdatatype.TDObject.parseRSRCDataHeader(bldata)
            if (self.po.verbose > 2):
                print("{:s}: Block {} LinkObj {} TypeDesc at 0x{:04x}, type 0x{:02x} flags 0x{:02x} len {:d}"\
                  .format(self.vi.src_fname, self.blockref[0], self.ident, obj_pos, obj_type, obj_flags, obj_len))
            # Some unusual operations are required on the size in order to get real size; zero means no TD at all
            if obj_len > 0:
                obj_len = 2 * (obj_len + 1)

                bldata.seek(obj_pos)
                clientTD = SimpleNamespace()
                clientTD.index = -1
                clientTD.nested = None # TODO parse the TD and store there, remove the unparsed data
                clientTD.nested_data = bldata.read(obj_len)
                clientTD.flags = 0 # Only Type Mapped entries have it non-zero
                self.typedLinkTD = clientTD
            else:
                bldata.seek(obj_pos+2)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-obj_pos, 1, "TypedLinkSaveInfo.TD")

            start_pos = bldata.tell()
            self.linkSavePathRef = self.parsePathRef(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "BasicLinkSaveInfo.PathRef")
            if (bldata.tell() % 2) > 0:
                bldata.read(2 - (bldata.tell() % 2)) # Padding bytes

            self.parseVILinkRefInfo(bldata)
        pass

    def prepareTypedLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))

            clientTD = self.typedLinkTD
            data_buf += prepareVariableSizeFieldU2p2(clientTD.index)

            data_buf += self.prepareVILinkRefInfo(start_offs+len(data_buf))

            if isGreaterOrEqVersion(ver, 12,0,0,3):
                data_buf +=  int(self.typedLinkFlags).to_bytes(4, byteorder='big', signed=False)
        else:
            # We expect only one name in the list
            for qualName in self.linkSaveQualName:
                data_buf += preparePStr(qualName, 2, self.po)

            data_buf += self.prepareLinkOffsetList(self.typedLinkOffsetList, start_offs+len(data_buf))

            clientTD = self.typedLinkTD
            if clientTD is None:
                data_buf += int(0).to_bytes(2, byteorder='big', signed=False)
            elif clientTD.index == -1:
                data_buf += clientTD.nested_data
            else:
                raise AttributeError("TypedLinkSaveInfo refers to TD via index, but we are using LV7 format with no VCTP")

            data_buf += self.linkSavePathRef.prepareRSRCData()
            if (start_offs+len(data_buf)) % 2 > 0:
                padding_len = 2 - ((start_offs+len(data_buf)) % 2)
                data_buf += (b'\0' * padding_len)

            data_buf += self.prepareVILinkRefInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXMLTypedLinkSaveInfo(self, lnkobj_elem):
        self.clearTypedLinkSaveInfo()

        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        self.initWithXMLVILinkRefInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "TypeDesc"):
                tmpVal = subelem.get("TypeID")
                if tmpVal is not None:
                    clientTD = SimpleNamespace()
                    clientTD.index = int(tmpVal, 0)
                    clientTD.flags = 0 # Only Type Mapped entries have it non-zero
                    if clientTD.index == -1:
                        clientTD.nested_data = subelem.text.encode(self.vi.textEncoding)
                    self.typedLinkTD = clientTD
            elif (subelem.tag == "TypedLinkOffsetList"):
                self.typedLinkOffsetList = self.initWithXMLLinkOffsetList(subelem)
            else:
                pass # No exception here - parent may define more tags

        typedLinkFlags = lnkobj_elem.get("TypedLinkFlags")
        if typedLinkFlags is not None:
            self.typedLinkFlags = int(typedLinkFlags, 0)

    def exportXMLTypedLinkSaveInfo(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        self.exportXMLVILinkRefInfo(lnkobj_elem, fname_base)

        clientTD = self.typedLinkTD
        if clientTD is None:
            subelem = ET.SubElement(lnkobj_elem, "TypeDesc")
        elif clientTD.index >= 0:
            subelem = ET.SubElement(lnkobj_elem, "TypeDesc")
            subelem.set("TypeID", "{:d}".format(clientTD.index))
        else:
            subelem = ET.SubElement(lnkobj_elem, "TypeDesc")
            subelem.set("TypeID", "{:d}".format(clientTD.index))
            subelem.text = clientTD.nested_data.decode(self.vi.textEncoding)

        if isSmallerVersion(ver, 8,0,0,1):
            subelem = ET.SubElement(lnkobj_elem, "TypedLinkOffsetList")
            self.exportXMLLinkOffsetList(self.typedLinkOffsetList, subelem)

        lnkobj_elem.set("TypedLinkFlags", "{:d}".format(self.typedLinkFlags))

    def parseLinkOffsetList(self, bldata):
        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 4, 1, "LinkOffsetList.Count")
        if count > self.po.typedesc_list_limit:
            raise RuntimeError("{:s} {} Offset List length {} exceeds limit"\
              .format(type(self).__name__, self.ident, count))
        offsetList = []
        for i in range(count):
            offs = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.appendPrintMapEntry(bldata.tell(), 4, 1, "LinkOffsetList.Offset[{}]".format(i))
            offsetList.append(offs)
        return offsetList

    def prepareLinkOffsetList(self, offsetList, start_offs):
        data_buf = b''
        data_buf += len(offsetList).to_bytes(4, byteorder='big', signed=False)
        for offs in offsetList:
            data_buf += int(offs).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def initWithXMLLinkOffsetList(self, ol_elem):
        offsetList = []
        for subelem in ol_elem:
            if (subelem.tag == "Offset"):
                offs = int(subelem.text,0)
                offsetList.append(offs)
            else:
                raise AttributeError("LinkOffsetList contains unexpected tag '{}'".format(subelem.tag))
        return offsetList

    def exportXMLLinkOffsetList(self, items, ol_elem):
        for offs in items:
            subelem = ET.SubElement(ol_elem,"Offset")
            subelem.text = "0x{:04X}".format(offs)
        pass

    def clearOffsetLinkSaveInfo(self):
        self.clearTypedLinkSaveInfo()
        self.offsetList = []

    def parseOffsetLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearOffsetLinkSaveInfo()

        start_pos = bldata.tell()
        self.parseTypedLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "OffsetLinkSaveInfo.TypedLinkSaveInfo")

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            start_pos = bldata.tell()
            self.offsetList = self.parseLinkOffsetList(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "OffsetLinkSaveInfo.OffsetList")
        pass

    def prepareOffsetLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.prepareTypedLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            data_buf += self.prepareLinkOffsetList(self.offsetList, start_offs+len(data_buf))
        return data_buf

    def initWithXMLOffsetLinkSaveInfo(self, lnkobj_elem):
        self.clearOffsetLinkSaveInfo()

        self.initWithXMLTypedLinkSaveInfo(lnkobj_elem)
        for subelem in lnkobj_elem:
            if (subelem.tag == "LinkOffsetList"):
                self.offsetList = self.initWithXMLLinkOffsetList(subelem)
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXMLOffsetLinkSaveInfo(self, lnkobj_elem, fname_base):
        self.exportXMLTypedLinkSaveInfo(lnkobj_elem, fname_base)

        subelem = ET.SubElement(lnkobj_elem, "LinkOffsetList")
        self.exportXMLLinkOffsetList(self.offsetList, subelem)

    def clearHeapToVILinkSaveInfo(self):
        self.viLSPathRef = None

    def parseHeapToVILinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearHeapToVILinkSaveInfo()

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "HeapToVILinkSaveInfo.OffsetLinkSaveInfo")

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            start_pos = bldata.tell()
            self.viLSPathRef = self.parsePathRef(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "HeapToVILinkSaveInfo.PathRef")

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.offsetList, self.viLSPathRef))
        pass

    def prepareHeapToVILinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            data_buf += self.viLSPathRef.prepareRSRCData()
        return data_buf

    def initWithXMLHeapToVILinkSaveInfo(self, lnkobj_elem):
        self.clearHeapToVILinkSaveInfo()

        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)
        for subelem in lnkobj_elem:
            if (subelem.tag == "VILSPathRef"):
                self.viLSPathRef = self.initWithXMLPathRef(subelem)
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXMLHeapToVILinkSaveInfo(self, lnkobj_elem, fname_base):
        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)

        if self.viLSPathRef is not None:
            subelem = ET.SubElement(lnkobj_elem,"VILSPathRef")
            self.viLSPathRef.exportXML(subelem, fname_base)

    def clearUDClassAPILinkCache(self):
        self.apiLinkLibVersion = 0
        self.apiLinkIsInternal = 0
        self.apiLinkBool2 = 1
        self.apiLinkCallParentNodes = 0
        self.apiLinkContent = b''

    def parseUDClassAPILinkCache(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearUDClassAPILinkCache()

        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            self.apiLinkLibVersion = int.from_bytes(bldata.read(8), byteorder='big', signed=False)
            self.appendPrintMapEntry(bldata.tell(), 8, 1, "UDClassAPILinkCache.LibVersion")
        else:
            self.apiLinkLibVersion = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.appendPrintMapEntry(bldata.tell(), 4, 1, "UDClassAPILinkCache.LibVersion")

        if isSmallerVersion(ver, 8,0,0,4):
            bldata.read(4)
            self.appendPrintMapEntry(bldata.tell(), 4, 1, "UDClassAPILinkCache.Padding")

        self.apiLinkIsInternal = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 1, 1, "UDClassAPILinkCache.IsInternal")
        if isGreaterOrEqVersion(ver, 8,1,0,2):
            self.apiLinkBool2 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.appendPrintMapEntry(bldata.tell(), 1, 1, "UDClassAPILinkCache.Bool2")

        if isGreaterOrEqVersion(ver, 9,0,0,2):
            self.apiLinkCallParentNodes = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.appendPrintMapEntry(bldata.tell(), 1, 1, "UDClassAPILinkCache.CallParentNodes")
        else:
            self.apiLinkCallParentNodes = 0

        self.apiLinkContent = readLStr(bldata, 1, self.po)
        self.appendPrintMapEntry(bldata.tell(), 4+len(self.apiLinkContent), 1, "UDClassAPILinkCache.Content")

    def prepareUDClassAPILinkCache(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if (start_offs+len(data_buf)) % 4 > 0:
            padding_len = 4 - ((start_offs+len(data_buf)) % 4)
            data_buf += (b'\0' * padding_len) # Padding bytes

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            data_buf += int(self.apiLinkLibVersion).to_bytes(8, byteorder='big', signed=False)
        else:
            data_buf += int(self.apiLinkLibVersion).to_bytes(4, byteorder='big', signed=False)

        if isSmallerVersion(ver, 8,0,0,4):
            data_buf += (b'\0' * 4)

        data_buf += int(self.apiLinkIsInternal).to_bytes(1, byteorder='big', signed=False)
        if isGreaterOrEqVersion(ver, 8,1,0,2):
            data_buf += int(self.apiLinkBool2).to_bytes(1, byteorder='big', signed=False)

        if isGreaterOrEqVersion(ver, 9,0,0,2):
            data_buf += int(self.apiLinkCallParentNodes).to_bytes(1, byteorder='big', signed=False)

        data_buf += prepareLStr(self.apiLinkContent, 1, self.po)
        return data_buf

    def initWithXMLUDClassAPILinkCache(self, lnkobj_elem):
        self.clearUDClassAPILinkCache()

        self.apiLinkLibVersion = int(lnkobj_elem.get("APILinkLibVersion"), 0)
        self.apiLinkIsInternal = int(lnkobj_elem.get("APILinkIsInternal"), 0)
        self.apiLinkBool2 = int(lnkobj_elem.get("APILinkBool2"), 0)
        self.apiLinkCallParentNodes = int(lnkobj_elem.get("APILinkCallParentNodes"), 0)

        for subelem in lnkobj_elem:
            if (subelem.tag == "APILinkContent"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.apiLinkContent = elem_text.encode(self.vi.textEncoding)
                else:
                    self.apiLinkContent = b''
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXMLUDClassAPILinkCache(self, lnkobj_elem, fname_base):
        lnkobj_elem.set("APILinkLibVersion", "{:d}".format(self.apiLinkLibVersion))
        lnkobj_elem.set("APILinkIsInternal", "{:d}".format(self.apiLinkIsInternal))
        lnkobj_elem.set("APILinkBool2", "{:d}".format(self.apiLinkBool2))
        lnkobj_elem.set("APILinkCallParentNodes", "{:d}".format(self.apiLinkCallParentNodes))

        subelem = ET.SubElement(lnkobj_elem,"APILinkContent")
        name_text = self.apiLinkContent.decode(self.vi.textEncoding)
        ET.safe_store_element_text(subelem, name_text)

    def clearUDClassHeapAPISaveInfo(self):
        self.clearBasicLinkSaveInfo()
        self.clearUDClassAPILinkCache()
        self.apiLinkCacheList = []

    def parseUDClassHeapAPISaveInfo(self, bldata):
        self.clearUDClassHeapAPISaveInfo()
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,0,0,3):
            start_pos = bldata.tell()
            self.parseBasicLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "UDClassHeapAPISaveInfo.BasicLinkSaveInfo")

            start_pos = bldata.tell()
            self.parseUDClassAPILinkCache(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "UDClassHeapAPISaveInfo.UDClassAPILinkCache")
        else:
            start_pos = bldata.tell()
            self.parseBasicLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "UDClassHeapAPISaveInfo.BasicLinkSaveInfo")
            self.apiLinkLibVersion = 0
            self.apiLinkIsInternal = 0
            self.apiLinkBool2 = 1

        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes

        # Not sure if that list is OffsetList, but has the same structure
        start_pos = bldata.tell()
        self.apiLinkCacheList = self.parseLinkOffsetList(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "UDClassHeapAPISaveInfo.CacheList")

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.apiLinkLibVersion, self.apiLinkCacheList))
        pass

    def prepareUDClassHeapAPISaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.apiLinkLibVersion, self.apiLinkCacheList))

        if isGreaterOrEqVersion(ver, 8,0,0,3):
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
            data_buf += self.prepareUDClassAPILinkCache(start_offs+len(data_buf))
        else:
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))

        if (start_offs+len(data_buf)) % 4 > 0:
            padding_len = 4 - ((start_offs+len(data_buf)) % 4)
            data_buf += (b'\0' * padding_len) # Padding bytes

        # Not sure if that list is OffsetList, but has the same structure
        data_buf += self.prepareLinkOffsetList(self.apiLinkCacheList, start_offs+len(data_buf))
        return data_buf

    def initWithXMLUDClassHeapAPISaveInfo(self, lnkobj_elem):
        self.clearUDClassHeapAPISaveInfo()

        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        self.initWithXMLUDClassAPILinkCache(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","APILinkContent",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "APILinkCacheList"):
                self.apiLinkCacheList = self.initWithXMLLinkOffsetList(subelem)
            else:
                raise AttributeError("UDClassHeapAPISaveInfo contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXMLUDClassHeapAPISaveInfo(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,0,0,3):
            self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
            self.exportXMLUDClassAPILinkCache(lnkobj_elem, fname_base)
        else:
            self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)

        subelem = ET.SubElement(lnkobj_elem, "APILinkCacheList")
        self.exportXMLLinkOffsetList(self.apiLinkCacheList, subelem)

    def clearUDClassVIAPISaveInfo(self):
        self.clearBasicLinkSaveInfo()
        self.clearUDClassAPILinkCache()

    def parseUDClassVIAPISaveInfo(self, bldata):
        self.clearUDClassVIAPISaveInfo()

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "UDClassVIAPISaveInfo.BasicLinkSaveInfo")

        start_pos = bldata.tell()
        self.parseUDClassAPILinkCache(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "UDClassVIAPISaveInfo.UDClassAPILinkCache")

    def prepareUDClassVIAPISaveInfo(self, start_offs):
        data_buf = b''
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        data_buf += self.prepareUDClassAPILinkCache(start_offs+len(data_buf))
        return data_buf

    def initWithXMLUDClassVIAPISaveInfo(self, lnkobj_elem):
        self.clearUDClassVIAPISaveInfo()
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        self.initWithXMLUDClassAPILinkCache(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","APILinkContent",):
                pass # These tags are parsed elswhere
            else:
                raise AttributeError("UDClassVIAPISaveInfo contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXMLUDClassVIAPISaveInfo(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        self.exportXMLUDClassAPILinkCache(lnkobj_elem, fname_base)

    def clearGILinkInfo(self):
        self.giLinkProp1 = 0
        self.giLinkProp2 = 0
        self.giLinkProp3 = 0
        self.giLinkProp4 = 0
        self.giLinkProp5 = 0

    def parseGILinkInfo(self, bldata):
        self.clearGILinkInfo()
        self.giLinkProp1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 2, 1, "GILinkInfo.Prop1")
        self.giLinkProp2 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 2, 1, "GILinkInfo.Prop2")
        self.giLinkProp3 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 2, 1, "GILinkInfo.Prop3")
        self.giLinkProp4 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 2, 1, "GILinkInfo.Prop4")
        self.giLinkProp5 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 4, 1, "GILinkInfo.Prop5")

    def prepareGILinkInfo(self, start_offs):
        data_buf = b''
        data_buf += int(self.giLinkProp1).to_bytes(2, byteorder='big', signed=False)
        data_buf += int(self.giLinkProp2).to_bytes(2, byteorder='big', signed=False)
        data_buf += int(self.giLinkProp3).to_bytes(2, byteorder='big', signed=False)
        data_buf += int(self.giLinkProp4).to_bytes(2, byteorder='big', signed=False)
        data_buf += int(self.giLinkProp5).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def initWithXMLGILinkInfo(self, lnkobj_elem):
        self.clearGILinkInfo()
        self.giLinkProp1 = int(lnkobj_elem.get("GILinkProp1"), 0)
        self.giLinkProp2 = int(lnkobj_elem.get("GILinkProp2"), 0)
        self.giLinkProp3 = int(lnkobj_elem.get("GILinkProp3"), 0)
        self.giLinkProp4 = int(lnkobj_elem.get("GILinkProp4"), 0)
        self.giLinkProp5 = int(lnkobj_elem.get("GILinkProp5"), 0)

    def exportXMLGILinkInfo(self, lnkobj_elem, fname_base):
        lnkobj_elem.set("GILinkProp1", "{:d}".format(self.giLinkProp1))
        lnkobj_elem.set("GILinkProp2", "{:d}".format(self.giLinkProp2))
        lnkobj_elem.set("GILinkProp3", "{:d}".format(self.giLinkProp3))
        lnkobj_elem.set("GILinkProp4", "{:d}".format(self.giLinkProp4))
        lnkobj_elem.set("GILinkProp5", "{:d}".format(self.giLinkProp5))

    def clearGILinkSaveInfo(self):
        self.clearBasicLinkSaveInfo()
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

    def parseGILinkSaveInfo(self, bldata):
        self.clearGILinkSaveInfo()
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,0,0,2):
            start_pos = bldata.tell()
            self.parseBasicLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "GILinkSaveInfo.BasicLinkSaveInfo")
        else:
            start_pos = bldata.tell()
            self.parseOffsetLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "GILinkSaveInfo.OffsetLinkSaveInfo")

        start_pos = bldata.tell()
        self.parseGILinkInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "GILinkSaveInfo.GILinkInfo")

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.offsetList, self.giLinkProp5))
        pass

    def prepareGILinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.offsetList, self.giLinkProp5))

        if isGreaterOrEqVersion(ver, 8,0,0,2):
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        else:
            data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        data_buf += self.prepareGILinkInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXMLGILinkSaveInfo(self, lnkobj_elem):
        self.clearGILinkSaveInfo()

        hasLinkSave = False
        hasLinkOffset = False
        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                hasLinkSave = True
            elif (subelem.tag == "LinkOffsetList"):
                hasLinkOffset = True
            else:
                raise AttributeError("GILinkSaveInfo contains unexpected tag '{}'".format(subelem.tag))
        if hasLinkSave:
            self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        if hasLinkOffset:
            self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)

        self.initWithXMLGILinkInfo(lnkobj_elem)

    def exportXMLGILinkSaveInfo(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,0,0,2):
            self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        else:
            self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)

        self.exportXMLGILinkInfo(lnkobj_elem, fname_base)

    def clearExtFuncLinkSaveInfo(self):
        self.clearOffsetLinkSaveInfo()
        self.extFuncStr = b''
        self.extFuncProp3 = 0
        self.extFuncProp4 = 0
        self.extFuncProp6 = 0

    def parseExtFuncLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearExtFuncLinkSaveInfo()

        if isGreaterOrEqVersion(ver, 8,0,0,3):
            start_pos = bldata.tell()
            self.parseBasicLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "ExtFuncLinkSaveInfo.BasicLinkSaveInfo")

            start_pos = bldata.tell()
            self.offsetList = self.parseLinkOffsetList(bldata) # reuse property from OffsetLinkSaveInfo
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "ExtFuncLinkSaveInfo.LinkOffsetList")

            self.extFuncStr = readPStr(bldata, 2, self.po)
            self.appendPrintMapEntry(bldata.tell(), 1+len(self.extFuncStr), 2, "ExtFuncLinkSaveInfo.Str")
            self.extFuncProp3 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.appendPrintMapEntry(bldata.tell(), 1, 2, "ExtFuncLinkSaveInfo.Prop3")
            self.extFuncProp4 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.appendPrintMapEntry(bldata.tell(), 1, 2, "ExtFuncLinkSaveInfo.Prop4")
            if isGreaterOrEqVersion(ver, 11,0,0,3):
                start_pos = bldata.tell()
                self.extFuncProp6 = self.parseBool(bldata)
                self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "ExtFuncLinkSaveInfo.Prop6")
        else:
            start_pos = bldata.tell()
            self.parseOffsetLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "ExtFuncLinkSaveInfo.OffsetLinkSaveInfo")

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.offsetList, self.extFuncStr))
        pass

    def prepareExtFuncLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if isGreaterOrEqVersion(ver, 8,0,0,3):
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
            data_buf += self.prepareLinkOffsetList(self.offsetList, start_offs+len(data_buf))
            data_buf += preparePStr(self.extFuncStr, 2, self.po)
            data_buf += int(self.extFuncProp3).to_bytes(1, byteorder='big', signed=False)
            data_buf += int(self.extFuncProp4).to_bytes(1, byteorder='big', signed=False)
            if isGreaterOrEqVersion(ver, 11,0,0,3):
                data_buf += self.prepareBool(self.extFuncProp6)
        else:
            data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        return data_buf

    def initWithXMLExtFuncLinkSaveInfo(self, lnkobj_elem):
        self.clearExtFuncLinkSaveInfo()

        propTmpStr = lnkobj_elem.get("ExtFuncProp3")
        if propTmpStr is not None:
            self.extFuncProp3 = int(propTmpStr, 0)
        propTmpStr = lnkobj_elem.get("ExtFuncProp4")
        if propTmpStr is not None:
            self.extFuncProp4 = int(propTmpStr, 0)
        propTmpStr = lnkobj_elem.get("ExtFuncProp6")
        if propTmpStr is not None:
            self.extFuncProp6 = int(propTmpStr, 0)

        hasLinkSave = False
        hasTypedLink = False
        linkOffset_elem = None
        hasExtFuncLink = False
        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                hasLinkSave = True
            elif (subelem.tag == "LinkOffsetList"):
                linkOffset_elem = subelem
            elif subelem.tag in ("TypeDesc","TypedLinkOffsetList",):
                hasTypedLink = True
            elif (subelem.tag == "ExtFuncLinkStr"):
                hasExtFuncLink = True
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.extFuncStr = elem_text.encode(self.vi.textEncoding)
                else:
                    self.extFuncStr = b''
            else:
                pass # No exception here - parent may define more tags
        hasLinkOffset = (linkOffset_elem is not None)
        if hasLinkSave and hasLinkOffset and hasTypedLink:
            self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)
        elif hasLinkSave and hasLinkOffset and hasExtFuncLink:
            self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
            self.offsetList = self.initWithXMLLinkOffsetList(linkOffset_elem)
        else:
            raise AttributeError("Some tags required for ExtFuncLinkSaveInfo are missing in '{}'".format(self.ident))
        pass

    def exportXMLExtFuncLinkSaveInfo(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,0,0,3):
            self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)

            subelem = ET.SubElement(lnkobj_elem, "LinkOffsetList")
            self.exportXMLLinkOffsetList(self.offsetList, subelem)

            subelem = ET.SubElement(lnkobj_elem,"ExtFuncLinkStr")
            name_text = self.extFuncStr.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, name_text)

            lnkobj_elem.set("ExtFuncProp3", "{:d}".format(self.extFuncProp3))
            lnkobj_elem.set("ExtFuncProp4", "{:d}".format(self.extFuncProp4))
            if isGreaterOrEqVersion(ver, 11,0,0,3):
                lnkobj_elem.set("ExtFuncProp6", "{:d}".format(self.extFuncProp6))
        else:
            self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)
        pass

    def clearAXLinkSaveInfo(self):
        self.clearOffsetLinkSaveInfo()
        self.axLinkStr = b''

    def parseAXLinkSaveInfo(self, bldata):
        self.clearAXLinkSaveInfo()

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "AXLinkSaveInfo.OffsetLinkSaveInfo")

        self.axLinkStr = bldata.read(40)
        self.appendPrintMapEntry(bldata.tell(), 40, 1, \
          "AXLinkSaveInfo.Str")

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.offsetList, self.axLinkStr))
        pass

    def prepareAXLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))
        data_buf += self.axLinkStr[:40]

        return data_buf

    def initWithXMLAXLinkSaveInfo(self, lnkobj_elem):
        self.clearAXLinkSaveInfo()

        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","LinkOffsetList","TypeDesc","TypedLinkOffsetList",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "AXLinkStr"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.axLinkStr = elem_text.encode(self.vi.textEncoding)
                else:
                    self.axLinkStr = b''
            else:
                pass # No exception here - parent may define more tags

    def exportXMLAXLinkSaveInfo(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)

        if True:
            subelem = ET.SubElement(lnkobj_elem,"AXLinkStr")
            name_text = self.axLinkStr.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, name_text)
        pass

    def clearCCSymbolLinkRefInfo(self):
        from LVdatatype import TD_FULL_TYPE
        stringTd = LVdatatype.newTDObject(self.vi, self.blockref, -1, 0, TD_FULL_TYPE.String, self.po)
        self.ccSymbolStrDf = LVdatafill.newDataFillObjectWithTD(self.vi, self.blockref, -1, 0, stringTd, self.po)
        self.ccSymbolLinkBool = 0

    def parseCCSymbolLinkRefInfo(self, bldata):
        self.clearCCSymbolLinkRefInfo()

        start_pos = bldata.tell()
        self.ccSymbolStrDf.initWithRSRC(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "CCSymbolLinkRefInfo.StrDf")

        start_pos = bldata.tell()
        self.ccSymbolLinkBool = self.parseBool(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "CCSymbolLinkRefInfo.Bool")

        #raise NotImplementedError("LinkObj {} parsing not fully implemented"\
        #  .format(self.ident))
        pass

    def prepareCCSymbolLinkRefInfo(self, start_offs):
        data_buf = b''

        data_buf += self.ccSymbolStrDf.prepareRSRCData()
        data_buf += self.prepareBool(self.ccSymbolLinkBool)
        return data_buf

    def initWithXMLCCSymbolLinkRefInfo(self, lnkobj_elem):
        self.clearCCSymbolLinkRefInfo()

        propTmpStr = lnkobj_elem.get("CCSymbolLinkBool")
        if propTmpStr is not None:
            self.ccSymbolLinkBool = int(propTmpStr, 0)

        stringDf_tag = self.ccSymbolStrDf.getXMLTagName()
        for subelem in lnkobj_elem:
            if (subelem.tag == "CCSymbolLinkStr"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.ccSymbolLinkStr = elem_text.encode(self.vi.textEncoding)
                else:
                    self.ccSymbolLinkStr = b''
            elif (subelem.tag == stringDf_tag):
                df = self.ccSymbolStrDf
                df.initWithXML(subelem)
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXMLCCSymbolLinkRefInfo(self, lnkobj_elem, fname_base):
        df = self.ccSymbolStrDf
        subelem = ET.SubElement(lnkobj_elem, df.getXMLTagName())
        df.exportXML(subelem, fname_base)

        lnkobj_elem.set("CCSymbolLinkBool", "{:d}".format(self.ccSymbolLinkBool))

    def clearHeapToFileSaveInfo(self):
        self.clearOffsetLinkSaveInfo()
        self.fileSaveStr = b''
        self.fileSaveProp3 = 0

    def parseHeapToFileSaveInfo(self, bldata):
        self.clearHeapToFileSaveInfo()

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "HeapToFileSaveInfo.BasicLinkSaveInfo")

        start_pos = bldata.tell()
        self.fileSaveStr = readLStr(bldata, 1, self.po)
        if (bldata.tell() % 4) > 0:
            bldata.read(4 - (bldata.tell() % 4)) # Padding bytes
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "HeapToFileSaveInfo.Str")

        self.fileSaveProp3 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 4, 1, "HeapToFileSaveInfo.Prop3")

        start_pos = bldata.tell()
        self.offsetList = self.parseLinkOffsetList(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "HeapToFileSaveInfo.OffsetList")

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.fileSaveStr, self.offsetList))
        pass

    def prepareHeapToFileSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        data_buf += prepareLStr(self.fileSaveStr, 1, self.po)
        if (start_offs+len(data_buf)) % 4 > 0:
            padding_len = 4 - ((start_offs+len(data_buf)) % 4)
            data_buf += (b'\0' * padding_len)
        data_buf += int(self.fileSaveProp3).to_bytes(4, byteorder='big', signed=False)
        data_buf += self.prepareLinkOffsetList(self.offsetList, start_offs+len(data_buf))
        return data_buf

    def initWithXMLHeapToFileSaveInfo(self, lnkobj_elem):
        self.clearHeapToFileSaveInfo()

        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)

        propTmpStr = lnkobj_elem.get("FileSaveProp3")
        if propTmpStr is not None:
            self.fileSaveProp3 = int(propTmpStr, 0)

        for subelem in lnkobj_elem:
            if (subelem.tag == "LinkOffsetList"):
                self.offsetList = self.initWithXMLLinkOffsetList(subelem)
            elif (subelem.tag == "FileSaveStr"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.fileSaveStr = elem_text.encode(self.vi.textEncoding)
                else:
                    self.fileSaveStr = b''
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXMLHeapToFileSaveInfo(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)

        subelem = ET.SubElement(lnkobj_elem,"FileSaveStr")
        name_text = self.fileSaveStr.decode(self.vi.textEncoding)
        ET.safe_store_element_text(subelem, name_text)

        lnkobj_elem.set("FileSaveProp3", "{:d}".format(self.fileSaveProp3))

        subelem = ET.SubElement(lnkobj_elem, "LinkOffsetList")
        self.exportXMLLinkOffsetList(self.offsetList, subelem)

    def clearDNHeapLinkSaveInfo(self):
        self.viLSPathRef = None

    def parseDNHeapLinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearDNHeapLinkSaveInfo()

        if isGreaterOrEqVersion(ver, 8,5,0,1):
            start_pos = bldata.tell()
            self.parseOffsetLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "DNHeapLinkSaveInfo.OffsetLinkSaveInfo")

            if isGreaterOrEqVersion(ver, 10,0,0,1):
                if (bldata.tell() % 2) > 0:
                    bldata.read(2 - (bldata.tell() % 2)) # Padding bytes
                start_pos = bldata.tell()
                self.viLSPathRef = self.parsePathRef(bldata)
                self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, "DNHeapLinkSaveInfo.PathRef")

        else:
            raise NotImplementedError("Unsupported DNHeapLinkSaveInfo read in ver=0x{:06X} older than LV8.5"\
              .format(encodeVersion(ver)))

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.offsetList, self.viLSPathRef))
        pass

    def prepareDNHeapLinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if isGreaterOrEqVersion(ver, 8,5,0,1):
            data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

            if isGreaterOrEqVersion(ver, 10,0,0,1):
                if (start_offs+len(data_buf)) % 2 > 0:
                    padding_len = 2 - ((start_offs+len(data_buf)) % 2)
                    data_buf += (b'\0' * padding_len)
                data_buf += self.viLSPathRef.prepareRSRCData()

        return data_buf

    def initWithXMLDNHeapLinkSaveInfo(self, lnkobj_elem):
        self.clearDNHeapLinkSaveInfo()

        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)
        for subelem in lnkobj_elem:
            if (subelem.tag == "VILSPathRef"):
                self.viLSPathRef = self.initWithXMLPathRef(subelem)
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXMLDNHeapLinkSaveInfo(self, lnkobj_elem, fname_base):
        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)

        if self.viLSPathRef is not None:
            subelem = ET.SubElement(lnkobj_elem,"VILSPathRef")
            self.viLSPathRef.exportXML(subelem, fname_base)
        pass

    def clearDNVILinkSaveInfo(self):
        self.viLSPathRef = None

    def parseDNVILinkSaveInfo(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearDNVILinkSaveInfo()

        if isGreaterOrEqVersion(ver, 8,5,0,1):
            start_pos = bldata.tell()
            self.parseBasicLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "DNVILinkSaveInfo.BasicLinkSaveInfo")

            if isGreaterOrEqVersion(ver, 10,0,0,1):
                if (bldata.tell() % 2) > 0:
                    bldata.read(2 - (bldata.tell() % 2)) # Padding bytes
                start_pos = bldata.tell()
                self.viLSPathRef = self.parsePathRef(bldata)
                self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
                  "DNVILinkSaveInfo.PathRef")

        else:
            raise NotImplementedError("Unsupported DNVILinkSaveInfo read in ver=0x{:06X} older than LV8.5"\
              .format(encodeVersion(ver)))

        if (self.po.verbose > 2):
            print("{:s} {} content: {} {} {}"\
              .format(type(self).__name__, self.ident, self.linkSavePathRef, self.offsetList, self.viLSPathRef))
        pass

    def prepareDNVILinkSaveInfo(self, start_offs):
        ver = self.vi.getFileVersion()
        data_buf = b''

        if isGreaterOrEqVersion(ver, 8,5,0,1):
            data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))

            if isGreaterOrEqVersion(ver, 10,0,0,1):
                if (start_offs+len(data_buf)) % 2 > 0:
                    padding_len = 2 - ((start_offs+len(data_buf)) % 2)
                    data_buf += (b'\0' * padding_len)
                data_buf += self.viLSPathRef.prepareRSRCData()

        return data_buf

    def initWithXMLDNVILinkSaveInfo(self, lnkobj_elem):
        self.clearDNVILinkSaveInfo()

        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        for subelem in lnkobj_elem:
            if (subelem.tag == "VILSPathRef"):
                self.viLSPathRef = self.initWithXMLPathRef(subelem)
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXMLDNVILinkSaveInfo(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)

        if self.viLSPathRef is not None:
            subelem = ET.SubElement(lnkobj_elem,"VILSPathRef")
            self.viLSPathRef.exportXML(subelem, fname_base)
        pass

    def appendPrintMapEntry(self, relative_end_pos, entry_len, entry_align, sub_name):
        """ Add file map or section map entry for this object.
        """
        if self.po.print_map is None: return
        block = self.vi.get_or_raise(self.blockref[0])
        section = block.getSection(section_num=self.blockref[1])
        block.appendPrintMapEntry(section, relative_end_pos, entry_len, entry_align, \
          "LinkObject[{}].{}".format(self.ident,sub_name))

    def parseRSRCData(self, bldata):
        """ Parses binary data chunk from RSRC file.

        Receives file-like block data handle positioned at ident.
        The handle gives access to binary data which is associated with the link object.
        Parses the binary data, filling properties.
        """
        self.ident = bldata.read(4)

    def prepareRSRCData(self, avoid_recompute=False):
        """ Fills binary data chunk for RSRC file which is associated with the link object.

        Creates bytes with binary data, starting with ident.
        """
        data_buf = b''
        data_buf += self.ident[:4]
        raise NotImplementedError("LinkObj {} binary creation not implemented"\
          .format(self.ident))
        return data_buf

    def expectedRSRCSize(self):
        """ Returns data size expected to be returned by prepareRSRCData().
        """
        exp_whole_len = None
        return exp_whole_len

    def initWithXML(self, lnkobj_elem):
        """ Parses XML branch to fill properties of the link object.

        Receives ElementTree branch starting at tag associated with the link object.
        Parses the XML attributes, filling properties.
        """
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)

    def initWithXMLLate(self):
        """ Late part of link object loading from XML file

        Can access some basic data from other blocks and sections.
        Useful only if properties needs an update after other blocks are accessible.
        """
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        """ Fills XML branch with properties of the link object.

        Receives ElementTree branch starting at tag associated with the link object.
        Sets the XML attributes, using properties from self.
        """
        # Setting the tag is actually redundant - the caller should do that
        pretty_ident = getPrettyStrFromRsrcType(self.ident)
        lnkobj_elem.tag = pretty_ident
        raise NotImplementedError("LinkObj {} XML export not implemented"\
          .format(self.ident))

    def checkSanity(self):
        ret = True
        return ret


class LinkObjInstanceVIToOwnerVI(LinkObjBase):
    """ InstanceVI To OwnerVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjHeapToAssembly(LinkObjBase):
    """ Heap To Assembly Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearDNHeapLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseDNHeapLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.DNHeapLinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareDNHeapLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLDNHeapLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLDNHeapLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToAssembly(LinkObjBase):
    """ VI To Assembly Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearDNVILinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseDNVILinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.DNVILinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareDNVILinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLDNVILinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLDNVILinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToEIOLink(LinkObjBase):
    """ VI To EIO Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToEIOLink(LinkObjBase):
    """ Heap To EIO Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToCCSymbolLink(LinkObjBase):
    """ VI To CCSymbol Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()
        self.clearCCSymbolLinkRefInfo()
        self.ccSymbolStr = b''

    def parseRSRCData(self, bldata):
        self.clearBasicLinkSaveInfo()
        self.clearCCSymbolLinkRefInfo()
        self.ccSymbolStr = b''

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

        self.ccSymbolStr = readLStr(bldata, 1, self.po)
        self.appendPrintMapEntry(bldata.tell(), 4+len(self.ccSymbolStr), 1, \
          "{}.Str".format(type(self).__name__))

        start_pos = bldata.tell()
        self.parseCCSymbolLinkRefInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.CCSymbolLinkRefInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''

        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        data_buf += prepareLStr(self.ccSymbolStr, 1, self.po)
        data_buf += self.prepareCCSymbolLinkRefInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearBasicLinkSaveInfo()
        self.clearCCSymbolLinkRefInfo()
        self.ccSymbolStr = b''

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        self.initWithXMLCCSymbolLinkRefInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","LinkOffsetList","TypeDesc","String",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "CCSymbolStr"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.ccSymbolStr = elem_text.encode(self.vi.textEncoding)
                else:
                    self.ccSymbolStr = b''
            else:
                raise AttributeError("LinkObjHeapToCCSymbolLink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        self.exportXMLCCSymbolLinkRefInfo(lnkobj_elem, fname_base)

        subelem = ET.SubElement(lnkobj_elem,"CCSymbolStr")
        name_text = self.ccSymbolStr.decode(self.vi.textEncoding)
        ET.safe_store_element_text(subelem, name_text)


class LinkObjVIToFileLink(LinkObjBase):
    """ VI To File Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()
        self.fileLinkContent = b''
        self.fileLinkProp1 = 0

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        self.fileLinkContent = b''

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

        self.fileLinkContent = readLStr(bldata, 4, self.po)
        self.appendPrintMapEntry(bldata.tell(), 4+len(self.fileLinkContent), 4, \
          "{}.Content".format(type(self).__name__))

        self.fileLinkProp1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 4, 1, "{}.Prop1".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        data_buf += prepareLStr(self.fileLinkContent, 4, self.po)
        data_buf += int(self.fileLinkProp1).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.fileLinkContent = b''
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        self.fileLinkProp1 = int(lnkobj_elem.get("FileLinkProp1"), 0)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "FileLinkContent"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.fileLinkContent = elem_text.encode(self.vi.textEncoding)
                else:
                    self.fileLinkContent = b''
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        lnkobj_elem.set("FileLinkProp1", "{:d}".format(self.fileLinkProp1))
        subelem = ET.SubElement(lnkobj_elem,"FileLinkContent")
        name_text = self.fileLinkContent.decode(self.vi.textEncoding)
        ET.safe_store_element_text(subelem, name_text)


class LinkObjVIToFileNoWarnLink(LinkObjBase):
    """ VI To FileNoWarn Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToFilePathLink(LinkObjBase):
    """ VI To FilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToFilePathLink(LinkObjBase):
    """ Heap To FilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeToFilePathLink(LinkObjBase):
    """ XNode To FilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToGenVI(LinkObjBase):
    """ VI To Gen VI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToInstantiationVI(LinkObjBase):
    """ VI To InstantiationVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjInstantiationVIToGenVI(LinkObjBase):
    """ InstantiationVI To GenVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()
        self.genViGUID = b''

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        self.genViGUID = b''

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

        self.genViGUID = bldata.read(36)
        self.appendPrintMapEntry(bldata.tell(), 36, 1, \
          "{}.GUID".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        data_buf += self.genViGUID[:36]
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.genViGUID = b''
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "GenViGUID"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.genViGUID = bytes.fromhex(elem_text)
                else:
                    self.genViGUID = b''
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        subelem = ET.SubElement(lnkobj_elem,"GenViGUID")
        name_text = self.genViGUID.hex()
        ET.safe_store_element_text(subelem, name_text)


class LinkObjVIToVINamedLink(LinkObjBase):
    """ VI To VINamed Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToLibraryDataLink(LinkObjBase):
    """ VI To LibraryDataLink Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()
        self.libDataContent = b''
        self.libDataLinkProp2 = 0
        self.libDataLinkVarDF = None

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        self.libDataContent = b''
        self.libDataLinkProp2 = 0
        self.libDataLinkVarDF = None

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

        self.libDataContent = readLStr(bldata, 4, self.po)
        self.appendPrintMapEntry(bldata.tell(), 4+len(self.libDataContent), 4, \
          "{}.Content".format(type(self).__name__))

        #TODO Read content of LVVariant to self.libDataLinkVarDF

        start_pos = bldata.tell()
        self.libDataLinkProp2 = self.parseBool(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.Prop2".format(type(self).__name__))

        raise NotImplementedError("LinkObj {} parsing not fully implemented"\
          .format(self.ident))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        data_buf += prepareLStr(self.libDataContent, 4, self.po)
        #TODO add content of self.libDataLinkVarDF
        data_buf += self.prepareBool(self.libDataLinkProp2)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.libDataContent = b''
        self.libDataLinkProp2 = 0
        self.libDataLinkVarDF = None
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        self.libDataLinkProp2 = int(lnkobj_elem.get("LibDataLinkProp2"), 0)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "LibDataContent"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.libDataContent = elem_text.encode(self.vi.textEncoding)
                else:
                    self.libDataContent = b''
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        lnkobj_elem.set("LibDataLinkProp2", "{:d}".format(self.libDataLinkProp2))
        subelem = ET.SubElement(lnkobj_elem,"LibDataContent")
        name_text = self.libDataContent.decode(self.vi.textEncoding)
        ET.safe_store_element_text(subelem, name_text)


class LinkObjVIToMSLink(LinkObjBase):
    """ VI To MSLink Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()
        self.msLinkProp1 = 0
        self.msLinkQualName = []

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

        self.msLinkProp1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 4, 1, "{}.Prop1".format(type(self).__name__))

        start_pos = bldata.tell()
        self.msLinkQualName = readQualifiedName(bldata, self.po)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.QualName".format(type(self).__name__))

        #TODO Path and the rest after - parse
        raise NotImplementedError("LinkObj {} parsing not fully implemented"\
          .format(self.ident))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        data_buf += int(self.msLinkProp1).to_bytes(4, byteorder='big', signed=False)
        data_buf += prepareQualifiedName(self.msLinkQualName, self.po)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        self.msLinkProp1 = int(lnkobj_elem.get("MSLinkProp1"), 0)
        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "MSLinkQualName"):
                self.initWithXMLQualifiedName(self.msLinkQualName, subelem)
            else:
                pass # No exception here - parent may define more tags
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        lnkobj_elem.set("MSLinkProp1", "{:d}".format(self.msLinkProp1))
        subelem = ET.SubElement(lnkobj_elem,"MSLinkQualName")
        self.exportXMLQualifiedName(self.msLinkQualName, subelem)


class LinkObjTypeDefToCCLink(LinkObjBase):
    """ TypeDef To CustCtl Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToVILinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.clearHeapToVILinkSaveInfo()
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseHeapToVILinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.HeapToVILinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareHeapToVILinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearHeapToVILinkSaveInfo()
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToVILinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLHeapToVILinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjHeapToXCtlInterface(LinkObjBase):
    """ Heap To XCtlInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.OffsetLinkSaveInfo".format(type(self).__name__))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            start_pos = bldata.tell()
            self.parseGILinkInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.GILinkInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.ident[:4]
        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            data_buf += self.prepareGILinkInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)
        self.initWithXMLGILinkInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)
        self.exportXMLGILinkInfo(lnkobj_elem, fname_base)


class LinkObjXCtlToXInterface(LinkObjBase):
    """ XCtlToXInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.OffsetLinkSaveInfo".format(type(self).__name__))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            start_pos = bldata.tell()
            self.parseGILinkInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.GILinkInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.ident[:4]
        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            data_buf += self.prepareGILinkInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)
        self.initWithXMLGILinkInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)
        self.exportXMLGILinkInfo(lnkobj_elem, fname_base)


class LinkObjVIToXCtlInterface(LinkObjBase):
    """ VI To XCtlInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearGILinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseGILinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.GILinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareGILinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLGILinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLGILinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToXNodeInterface(LinkObjBase):
    """ VI To XNodeInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearGILinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseGILinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.GILinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareGILinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLGILinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLGILinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToXNodeProjectItemLink(LinkObjBase):
    """ VI To XNodeProjectItem Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToXNodeProjectItemLink(LinkObjBase):
    """ Heap To XNodeProjectItem Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjActiveXVIToTypeLib(LinkObjBase):
    """ ActiveXVIToTypeLib Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearAXLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseAXLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.AXLinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareAXLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLAXLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLAXLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToLib(LinkObjBase):
    """ VI To Lib Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjUDClassDDOToUDClassAPILink(LinkObjBase):
    """ UDClassDDO To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseUDClassHeapAPISaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.UDClassHeapAPISaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLUDClassHeapAPISaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLUDClassHeapAPISaveInfo(lnkobj_elem, fname_base)


class LinkObjDDODefaultDataToUDClassAPILink(LinkObjBase):
    """ DDODefaultData To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseUDClassHeapAPISaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.UDClassHeapAPISaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLUDClassHeapAPISaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLUDClassHeapAPISaveInfo(lnkobj_elem, fname_base)


class LinkObjHeapObjToUDClassAPILink(LinkObjBase):
    """ HeapObj To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseUDClassHeapAPISaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.UDClassHeapAPISaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLUDClassHeapAPISaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLUDClassHeapAPISaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToUDClassAPILink(LinkObjBase):
    """ VI To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseUDClassVIAPISaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.UDClassVIAPISaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassVIAPISaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLUDClassVIAPISaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLUDClassVIAPISaveInfo(lnkobj_elem, fname_base)


class LinkObjDataValueRefVIToUDClassAPILink(LinkObjBase):
    """ DataValueRefVI To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToVariableAbsoluteLink(LinkObjBase):
    """ VI To VariableAbsolute Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToVariableRelativeLink(LinkObjBase):
    """ VI To VariableRelative Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToVariableAbsoluteLink(LinkObjBase):
    """ Heap To VariableAbsolute Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToVariableRelativeLink(LinkObjBase):
    """ Heap To VariableRelative Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToVariableAbsoluteLink(LinkObjBase):
    """ DS To VariableAbsolute Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToVariableRelativeLink(LinkObjBase):
    """ DS To VariableRelative Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToDSLink(LinkObjBase):
    """ DS To DS Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearOffsetLinkSaveInfo()
        self.dsOffsetList = []

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearOffsetLinkSaveInfo()
        self.dsOffsetList = []

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.OffsetLinkSaveInfo".format(type(self).__name__))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            start_pos = bldata.tell()
            self.dsOffsetList = self.parseLinkOffsetList(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.OffsetList".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.ident[:4]
        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            data_buf += self.prepareLinkOffsetList(self.dsOffsetList, start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearOffsetLinkSaveInfo()
        self.dsOffsetList = []

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","LinkOffsetList","TypeDesc","TypedLinkOffsetList",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "DSOffsetList"):
                self.dsOffsetList = self.initWithXMLLinkOffsetList(subelem)
            else:
                raise AttributeError("LinkObjDSToDSLink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)

        subelem = ET.SubElement(lnkobj_elem, "DSOffsetList")
        self.exportXMLLinkOffsetList(self.dsOffsetList, subelem)
        pass


class LinkObjDSToExtFuncLink(LinkObjBase):
    """ DS To ExtFunc Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearExtFuncLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseExtFuncLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.ExtFuncLinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareExtFuncLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLExtFuncLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLExtFuncLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjDSToCINLink(LinkObjBase):
    """ DS To CIN Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToScriptLink(LinkObjBase):
    """ DS To Script Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToCallByRefLink(LinkObjBase):
    """ DS To CallByRef Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDSToStaticVILink(LinkObjBase):
    """ DS To StaticVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearOffsetLinkSaveInfo()

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearOffsetLinkSaveInfo()
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.OffsetLinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearOffsetLinkSaveInfo()
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToStdVILink(LinkObjBase):
    """ VI To StdVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearTypedLinkSaveInfo()
        self.stdViGUID = b''

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearTypedLinkSaveInfo()
        self.stdViGUID = b''

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseTypedLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.TypedLinkSaveInfo".format(type(self).__name__))

        if isGreaterOrEqVersion(ver, 10,0,0,2):
            start_pos = bldata.tell()
            hasGUID = self.parseBool(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.HasGUID".format(type(self).__name__))

            if hasGUID != 0:
                self.stdViGUID = bldata.read(36)
                self.appendPrintMapEntry(bldata.tell(), 36, 1, \
                  "{}.GUID".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareTypedLinkSaveInfo(start_offs+len(data_buf))
        if isGreaterOrEqVersion(ver, 10,0,0,2):
            hasGUID = 1 if len(self.stdViGUID) > 0 else 0
            data_buf += self.prepareBool(hasGUID)
            if hasGUID != 0:
                data_buf += self.stdViGUID[:36]
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.stdViGUID = b''
        self.initWithXMLTypedLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","TypeDesc","TypedLinkOffsetList",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "StdViGUID"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.stdViGUID = bytes.fromhex(elem_text)
                else:
                    self.stdViGUID = b''
            else:
                raise AttributeError("LinkObjVIToStdVILink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLTypedLinkSaveInfo(lnkobj_elem, fname_base)
        hasGUID = 1 if len(self.stdViGUID) > 0 else 0
        if hasGUID != 0:
            subelem = ET.SubElement(lnkobj_elem,"StdViGUID")
            name_text = self.stdViGUID.hex()
            ET.safe_store_element_text(subelem, name_text)
        pass


class LinkObjVIToProgRetLink(LinkObjBase):
    """ VI To ProgRet Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearTypedLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseTypedLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.TypedLinkSaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareTypedLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLTypedLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","TypeDesc","TypedLinkOffsetList",):
                pass # These tags are parsed elswhere
            else:
                raise AttributeError("LinkObjVIToProgRetLink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLTypedLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToPolyLink(LinkObjBase):
    """ VI To Poly Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearTypedLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseTypedLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.TypedLinkSaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareTypedLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLTypedLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","TypeDesc","TypedLinkOffsetList",):
                pass # These tags are parsed elswhere
            else:
                raise AttributeError("LinkObjVIToPolyLink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLTypedLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToCCLink(LinkObjBase):
    """ VI To CustCtl Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearTypedLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseTypedLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.TypedLinkSaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareTypedLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLTypedLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","TypeDesc","TypedLinkOffsetList",):
                pass # These tags are parsed elswhere
            else:
                raise AttributeError("LinkObjVIToCCLink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLTypedLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToStaticVILink(LinkObjBase):
    """ VI To StaticVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearTypedLinkSaveInfo()
        self.viLinkProp2 = 0

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseTypedLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.TypedLinkSaveInfo".format(type(self).__name__))

        self.viLinkProp2 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 4, 1, \
          "{}.Prop2".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareTypedLinkSaveInfo(start_offs+len(data_buf))
        data_buf += int(self.viLinkProp2).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLTypedLinkSaveInfo(lnkobj_elem)

        tmpProp = lnkobj_elem.get("VILinkProp2")
        if tmpProp is not None:
            self.viLinkProp2 = int(tmpProp, 0)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","TypeDesc","TypedLinkOffsetList",):
                pass # These tags are parsed elswhere
            else:
                raise AttributeError("LinkObjVIToStaticVILink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLTypedLinkSaveInfo(lnkobj_elem, fname_base)
        lnkobj_elem.set("VILinkProp2", "{:d}".format(self.viLinkProp2))


class LinkObjVIToAdaptiveVILink(LinkObjBase):
    """ VI To AdaptiveVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearTypedLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseTypedLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.TypedLinkSaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareTypedLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLTypedLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","TypeDesc","TypedLinkOffsetList",):
                pass # These tags are parsed elswhere
            else:
                raise AttributeError("LinkObjVIToAdaptiveVILink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLTypedLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjHeapToCCSymbolLink(LinkObjBase):
    """ Heap To CCSymbol Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearOffsetLinkSaveInfo()
        self.clearCCSymbolLinkRefInfo()
        self.ccSymbolStr = b''

    def parseRSRCData(self, bldata):
        self.clearOffsetLinkSaveInfo()
        self.clearCCSymbolLinkRefInfo()
        self.ccSymbolStr = b''

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.OffsetLinkSaveInfo".format(type(self).__name__))

        self.ccSymbolStr = readLStr(bldata, 1, self.po)
        self.appendPrintMapEntry(bldata.tell(), 4+len(self.ccSymbolStr), 1, \
          "{}.Str".format(type(self).__name__))

        start_pos = bldata.tell()
        self.parseCCSymbolLinkRefInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.CCSymbolLinkRefInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''

        data_buf += self.ident[:4]
        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))
        data_buf += prepareLStr(self.ccSymbolStr, 1, self.po)
        data_buf += self.prepareCCSymbolLinkRefInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearOffsetLinkSaveInfo()
        self.clearCCSymbolLinkRefInfo()
        self.ccSymbolStr = b''

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)
        self.initWithXMLCCSymbolLinkRefInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","LinkOffsetList","TypeDesc","TypedLinkOffsetList","String",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "CCSymbolStr"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.ccSymbolStr = elem_text.encode(self.vi.textEncoding)
                else:
                    self.ccSymbolStr = b''
            else:
                raise AttributeError("LinkObjHeapToCCSymbolLink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)
        self.exportXMLCCSymbolLinkRefInfo(lnkobj_elem, fname_base)

        subelem = ET.SubElement(lnkobj_elem,"CCSymbolStr")
        name_text = self.ccSymbolStr.decode(self.vi.textEncoding)
        ET.safe_store_element_text(subelem, name_text)


class LinkObjIUseToVILink(LinkObjBase):
    """ IUse To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToVILinkSaveInfo()
        self.iuseStr = b''

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearHeapToVILinkSaveInfo()
        self.iuseStr = b''

        self.ident = bldata.read(4)

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            start_pos = bldata.tell()
            self.parseHeapToVILinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.HeapToVILinkSaveInfo".format(type(self).__name__))
        else:
            start_pos = bldata.tell()
            self.parseOffsetLinkSaveInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.OffsetLinkSaveInfo".format(type(self).__name__))

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            self.iuseStr = readPStr(bldata, 2, self.po)
            self.appendPrintMapEntry(bldata.tell(), 1+len(self.iuseStr), 2, \
              "{}.Str".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.ident[:4]

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            data_buf += self.prepareHeapToVILinkSaveInfo(start_offs+len(data_buf))
        else:
            data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            data_buf += preparePStr(self.iuseStr, 2, self.po)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearHeapToVILinkSaveInfo()
        self.iuseStr = b''

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToVILinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef","LinkOffsetList","TypeDesc","TypedLinkOffsetList","VILSPathRef",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "IUseStr"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.iuseStr = elem_text.encode(self.vi.textEncoding)
                else:
                    self.iuseStr = b''
            else:
                raise AttributeError("LinkObjIUseToVILink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        ver = self.vi.getFileVersion()

        if isGreaterOrEqVersion(ver, 8,2,0,3):
            self.exportXMLHeapToVILinkSaveInfo(lnkobj_elem, fname_base)
        else:
            self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)

        if True:
            subelem = ET.SubElement(lnkobj_elem,"IUseStr")
            name_text = self.iuseStr.decode(self.vi.textEncoding)
            ET.safe_store_element_text(subelem, name_text)
        pass


class LinkObjPIUseToPolyLink(LinkObjBase):
    """ PIUse To Poly Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToVILinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.clearHeapToVILinkSaveInfo()

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseHeapToVILinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.HeapToVILinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareHeapToVILinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearHeapToVILinkSaveInfo()
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToVILinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLHeapToVILinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjNonVINonHeapToTypedefLink(LinkObjBase):
    """ NonVINonHeap To Typedef Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()
        self.typedLinkTD = None

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        self.typedLinkTD = None

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

        if True:
            start_pos = bldata.tell()
            clientTD = SimpleNamespace()
            clientTD.index = readVariableSizeFieldU2p2(bldata)
            clientTD.flags = 0 # Only Type Mapped entries have it non-zero
            self.typedLinkTD = clientTD
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.TD".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        if True:
            clientTD = self.typedLinkTD
            data_buf += prepareVariableSizeFieldU2p2(clientTD.index)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.typedLinkTD = None
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "TypeDesc"):
                clientTD = SimpleNamespace()
                clientTD.index = int(subelem.get("TypeID"), 0)
                clientTD.flags = 0 # Only Type Mapped entries have it non-zero
                self.typedLinkTD = clientTD
            else:
                raise AttributeError("LinkObjNonVINonHeapToTypedefLink contains unexpected tag '{}'".format(subelem.tag))

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        if True:
            clientTD = self.typedLinkTD
            subelem = ET.SubElement(lnkobj_elem, "TypeDesc")
            subelem.set("TypeID", "{:d}".format(clientTD.index))
        pass


class LinkObjCCSymbolLink(LinkObjBase):
    """ CCSymbol Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearBasicLinkSaveInfo()
        self.symbolLinkContent = b''
        self.symbolLinkProp2 = 0

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        self.symbolLinkContent = b''

        start_pos = bldata.tell()
        self.parseBasicLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.BasicLinkSaveInfo".format(type(self).__name__))

        self.symbolLinkContent = readLStr(bldata, 1, self.po)
        self.appendPrintMapEntry(bldata.tell(), 4+len(self.symbolLinkContent), 1, \
          "{}.Content".format(type(self).__name__))

        #TODO read StringTD
        start_pos = bldata.tell()
        self.symbolLinkProp2 = self.parseBool(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.Prop2".format(type(self).__name__))

        raise NotImplementedError("LinkObj {} parsing not fully implemented"\
          .format(self.ident))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareBasicLinkSaveInfo(start_offs+len(data_buf))
        data_buf += prepareLStr(self.symbolLinkContent, 1, self.po)
        #TODO add StringTD
        data_buf += self.prepareBool(self.symbolLinkProp2)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.symbolLinkContent = b''
        self.symbolLinkProp2 = 0
        self.initWithXMLBasicLinkSaveInfo(lnkobj_elem)
        self.symbolLinkProp2 = int(lnkobj_elem.get("SymbolLinkProp2"), 0)

        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkSaveQualName","LinkSavePathRef",):
                pass # These tags are parsed elswhere
            elif (subelem.tag == "SymbolLinkContent"):
                if subelem.text is not None:
                    elem_text = ET.unescape_safe_store_element_text(subelem.text)
                    self.symbolLinkContent = elem_text.encode(self.vi.textEncoding)
                else:
                    self.symbolLinkContent = b''
            else:
                raise AttributeError("LinkObjCCSymbolLink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLBasicLinkSaveInfo(lnkobj_elem, fname_base)
        lnkobj_elem.set("SymbolLinkProp2", "{:d}".format(self.symbolLinkProp2))
        subelem = ET.SubElement(lnkobj_elem,"SymbolLinkContent")
        name_text = self.symbolLinkContent.decode(self.vi.textEncoding)
        ET.safe_store_element_text(subelem, name_text)


class LinkObjHeapNamedLink(LinkObjBase):
    """ HeapNamed Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjFilePathLink(LinkObjBase):
    """ FilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjRCFilePathLink(LinkObjBase):
    """ RCFilePath Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToFileLink(LinkObjBase):
    """ Heap To File Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToFileSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseHeapToFileSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.HeapToFileSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareHeapToFileSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToFileSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLHeapToFileSaveInfo(lnkobj_elem, fname_base)


class LinkObjHeapToFileNoWarnLink(LinkObjBase):
    """ Heap To FileNoWarn Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToFileSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseHeapToFileSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.HeapToFileSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareHeapToFileSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToFileSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLHeapToFileSaveInfo(lnkobj_elem, fname_base)


class LinkObjVIToRCFileLink(LinkObjBase):
    """ VI To RCFile Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjIUseToInstantiationVILink(LinkObjBase):
    """ IUse To InstantiationVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjGenIUseToGenVILink(LinkObjBase):
    """ GenIUse To GenVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjNodeToEFLink(LinkObjBase):
    """ Node To ExtFunc Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearExtFuncLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseExtFuncLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.ExtFuncLinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareExtFuncLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLExtFuncLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLExtFuncLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjHeapToVILink(LinkObjBase):
    """ Heap To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjIUseToProgRetLink(LinkObjBase):
    """ IUse To ProgRet Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjStaticVIRefToVILink(LinkObjBase):
    """ StaticVIRef To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToVILinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.clearHeapToVILinkSaveInfo()
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseHeapToVILinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.HeapToVILinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareHeapToVILinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearHeapToVILinkSaveInfo()
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToVILinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLHeapToVILinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjNodeToCINLink(LinkObjBase):
    """ Node To CIN Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjNodeToScriptLink(LinkObjBase):
    """ Node To Script Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjStaticCallByRefToVILink(LinkObjBase):
    """ StaticCallByRef To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToRCFileLink(LinkObjBase):
    """ Heap To RCFile Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToFileSaveInfo()
        self.content = []

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearHeapToFileSaveInfo()
        self.content = []

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseHeapToFileSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.HeapToFileSaveInfo".format(type(self).__name__))

        count = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.appendPrintMapEntry(bldata.tell(), 4, 1, "{}.Count".format(type(self).__name__))
        for i in range(count):
            start_pos = bldata.tell()
            tditem = SimpleNamespace()
            tditem.clients, tditem.topType = LVdatatype.parseTDObject(self.vi, self.blockref, bldata, ver, self.po)
            tditem.prop2 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.content.append(tditem)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.TD[{}]".format(type(self).__name__,i))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareHeapToFileSaveInfo(start_offs+len(data_buf))
        data_buf += len(self.content).to_bytes(4, byteorder='big', signed=False)
        for tditem in self.content:
            data_buf += LVdatatype.prepareTDObject(self.vi, tditem.clients, tditem.topType, ver, self.po, avoid_recompute=avoid_recompute)
            data_buf += int(tditem.prop2).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearHeapToFileSaveInfo()
        self.content = []

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToFileSaveInfo(lnkobj_elem)
        for subelem in lnkobj_elem:
            if subelem.tag in ("LinkOffsetList", "FileSaveStr","LinkSaveQualName","LinkSavePathRef",):
                pass # These tags are parsed elswhere
            elif subelem.tag == "FileLinkTDList":
                tditem = SimpleNamespace()
                tditem.clients, tditem.topType = LVdatatype.initWithXMLTDObject(self.vi, self.blockref, subelem, self.po)
                tditem.prop2 = int(subelem.get("FileLinkProp2"), 0)
                self.content.append(tditem)
                pass
            else:
                raise AttributeError("LinkObjHeapToRCFileLink contains unexpected tag '{}'".format(subelem.tag))
        pass

    def initWithXMLLate(self):
        ver = self.vi.getFileVersion()
        super().initWithXMLLate()

        for tditem in self.content:
            LVdatatype.initWithXMLTDObjectLate(self.vi, tditem.clients, tditem.topType, ver, self.po)
        pass

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLHeapToFileSaveInfo(lnkobj_elem, fname_base)

        fname_obj = fname_base
        for i, tditem in enumerate(self.content):
            if len(self.content) > 1:
                fname_obj = "{:s}_{:04d}".format(fname_base, i)
            subelem = ET.SubElement(lnkobj_elem,"FileLinkTDList")
            LVdatatype.exportXMLTDObject(self.vi, tditem.clients, tditem.topType, subelem, fname_obj, self.po)
            subelem.set("FileLinkProp2", "{:d}".format(tditem.prop2))
        pass


class LinkObjHeapToVINamedLink(LinkObjBase):
    """ Heap To VINamed Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToLibraryDataLink(LinkObjBase):
    """ Heap To LibraryData Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMSNToMSLink(LinkObjBase):
    """ MSN To MS Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMSToMSImplVILink(LinkObjBase):
    """ MS To MSImplVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMSCallByRefToMSLink(LinkObjBase):
    """ MSCallByRef To MS Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMathScriptLink(LinkObjBase):
    """ MathScript Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjFBoxLineToInstantnVILink(LinkObjBase):
    """ FBoxLine To InstantiationVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToVILinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseHeapToVILinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.HeapToVILinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareHeapToVILinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToVILinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLHeapToVILinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjOMHeapToResource(LinkObjBase):
    """ OMHeap To Resource Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjOMVIToResource(LinkObjBase):
    """ OMVI To Resource Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjOMExtResLink(LinkObjBase):
    """ OMExtRes Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjGIToAbstractVI(LinkObjBase):
    """ GI To AbstractVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjGIToAbilityVI(LinkObjBase):
    """ GI To AbilityVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXIToPropertyVI(LinkObjBase):
    """ XI To PropertyVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXIToMethodVI(LinkObjBase):
    """ XI To MethodVI Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjGInterfaceLink(LinkObjBase):
    """ GInterface Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXInterfaceLink(LinkObjBase):
    """ XInterface Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXCtlInterfaceLink(LinkObjBase):
    """ XCtl Interface Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeInterfaceLink(LinkObjBase):
    """ XNode Interface Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjVIToContainerItemLink(LinkObjBase):
    """ VI To ContainerItem Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToContainerItemLink(LinkObjBase):
    """ Heap To ContainerItem Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjContainerItemLinkObj(LinkObjBase):
    """ ContainerItem Link Obj
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeProjectItemLinkObj(LinkObjBase):
    """ XNode ProjectItem Link Obj
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeToExtFuncLink(LinkObjBase):
    """ XNode To ExtFunc Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearExtFuncLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseExtFuncLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.ExtFuncLinkSaveInfo".format(type(self).__name__))
        # TODO I'm pretty sure some kind of string read is missing here..

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareExtFuncLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLExtFuncLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLExtFuncLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjXNodeToVILink(LinkObjBase):
    """ XNode To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearHeapToVILinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseHeapToVILinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.HeapToVILinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareHeapToVILinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLHeapToVILinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLHeapToVILinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjActiveXBDToTypeLib(LinkObjBase):
    """ ActiveX BD To TypeLib
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearAXLinkSaveInfo()

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseAXLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.AXLinkSaveInfo".format(type(self).__name__))

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareAXLinkSaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLAXLinkSaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLAXLinkSaveInfo(lnkobj_elem, fname_base)


class LinkObjActiveXTLibLinkObj(LinkObjBase):
    """ ActiveX TLib Link Obj
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjXNodeToXInterface(LinkObjBase):
    """ XNode To XInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.OffsetLinkSaveInfo".format(type(self).__name__))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            start_pos = bldata.tell()
            self.parseGILinkInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.GILinkInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.ident[:4]
        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            data_buf += self.prepareGILinkInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)
        self.initWithXMLGILinkInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)
        self.exportXMLGILinkInfo(lnkobj_elem, fname_base)


class LinkObjUDClassLibInheritsLink(LinkObjBase):
    """ UDClassLibInherits Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibToVILink(LinkObjBase):
    """ UDClassLib To VI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibToMemberVILink(LinkObjBase):
    """ UDClassLib To MemberVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibToPrivDataCtlLink(LinkObjBase):
    """ UDClassLib To PrivDataCtl Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToUDClassAPILink(LinkObjBase):
    """ Heap To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjDynInfoToUDClassAPILink(LinkObjBase):
    """ DynInfo To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseUDClassHeapAPISaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.UDClassHeapAPISaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLUDClassHeapAPISaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLUDClassHeapAPISaveInfo(lnkobj_elem, fname_base)


class LinkObjPropNodeItemToUDClassAPILink(LinkObjBase):
    """ PropNodeItem To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseUDClassHeapAPISaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.UDClassHeapAPISaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLUDClassHeapAPISaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLUDClassHeapAPISaveInfo(lnkobj_elem, fname_base)


class LinkObjCreOrDesRefToUDClassAPILink(LinkObjBase):
    """ CreateOrDestroyRef To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseUDClassHeapAPISaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.UDClassHeapAPISaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLUDClassHeapAPISaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLUDClassHeapAPISaveInfo(lnkobj_elem, fname_base)


class LinkObjDDOToUDClassAPILink(LinkObjBase):
    """ Data Display Object To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseUDClassHeapAPISaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.UDClassHeapAPISaveInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        data_buf = b''
        data_buf += self.ident[:4]
        data_buf += self.prepareUDClassHeapAPISaveInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLUDClassHeapAPISaveInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLUDClassHeapAPISaveInfo(lnkobj_elem, fname_base)


class LinkObjAPIToAPILink(LinkObjBase):
    """ API To API Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjAPIToNearestImplVILink(LinkObjBase):
    """ API To NearestImplVI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjAPIToChildAPILink(LinkObjBase):
    """ API To ChildAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToUDClassAPILink(LinkObjBase):
    """ Heap To UDClassAPI Link Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjMemberVIItem(LinkObjBase):
    """ MemberVIItem Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjUDClassLibrary(LinkObjBase):
    """ UDClassLibrary Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


class LinkObjHeapToXNodeInterface(LinkObjBase):
    """ Heap To XNodeInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

        self.ident = bldata.read(4)

        start_pos = bldata.tell()
        self.parseOffsetLinkSaveInfo(bldata)
        self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
          "{}.OffsetLinkSaveInfo".format(type(self).__name__))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            start_pos = bldata.tell()
            self.parseGILinkInfo(bldata)
            self.appendPrintMapEntry(bldata.tell(), bldata.tell()-start_pos, 1, \
              "{}.GILinkInfo".format(type(self).__name__))
        pass

    def prepareRSRCData(self, start_offs=0, avoid_recompute=False):
        ver = self.vi.getFileVersion()
        data_buf = b''

        data_buf += self.ident[:4]
        data_buf += self.prepareOffsetLinkSaveInfo(start_offs+len(data_buf))

        if isGreaterOrEqVersion(ver, 8,6,0,2):
            data_buf += self.prepareGILinkInfo(start_offs+len(data_buf))
        return data_buf

    def initWithXML(self, lnkobj_elem):
        self.clearOffsetLinkSaveInfo()
        self.clearGILinkInfo()

        self.ident = getRsrcTypeFromPrettyStr(lnkobj_elem.tag)
        self.initWithXMLOffsetLinkSaveInfo(lnkobj_elem)
        self.initWithXMLGILinkInfo(lnkobj_elem)

    def exportXML(self, lnkobj_elem, fname_base):
        self.exportXMLOffsetLinkSaveInfo(lnkobj_elem, fname_base)
        self.exportXMLGILinkInfo(lnkobj_elem, fname_base)


class LinkObjHeapToGInterface(LinkObjBase):
    """ Heap To GInterface Object Ref
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        self.ident = bldata.read(4)
        raise NotImplementedError("LinkObj {} parsing not implemented"\
          .format(self.ident))


def newLinkObject(vi, blockref, list_ident, ident, po):
    """ Calls proper constructor to create link object.
    """
    if ident in (b'IVOV',):
        ctor = LinkObjInstanceVIToOwnerVI
    elif ident in (b'DNDA',):
        ctor = LinkObjHeapToAssembly
    elif ident in (b'DNVA',):
        ctor = LinkObjVIToAssembly
    elif ident in (b'EiVr',):
        ctor = LinkObjVIToEIOLink
    elif ident in (b'HpEr',):
        ctor = LinkObjHeapToEIOLink
    elif ident in (b'V2CC',):
        ctor = LinkObjVIToCCSymbolLink
    elif ident in (b'VIFl',):
        ctor = LinkObjVIToFileLink
    elif ident in (b'VIFN',):
        ctor = LinkObjVIToFileNoWarnLink
    elif ident in (b'VIXF',):
        ctor = LinkObjVIToFilePathLink
    elif ident in (b'HOXF',):
        ctor = LinkObjHeapToFilePathLink
    elif ident in (b'XNFP',):
        ctor = LinkObjXNodeToFilePathLink
    elif ident in (b'VIGV',):
        ctor = LinkObjVIToGenVI
    elif ident in (b'VIIV',):
        ctor = LinkObjVIToInstantiationVI
    elif ident in (b'IVGV',):
        ctor = LinkObjInstantiationVIToGenVI
    elif ident in (b'VTVN',):
        ctor = LinkObjVIToVINamedLink
    elif ident in (b'V2LD',):
        ctor = LinkObjVIToLibraryDataLink
    elif ident in (b'VIMS',):
        ctor = LinkObjVIToMSLink
    elif ident in (b'TDCC',) or list_ident in (b'FPHP',) and ident in (b'LVCC',):
        ctor = LinkObjTypeDefToCCLink
    elif ident in (b'HXCI',):
        ctor = LinkObjHeapToXCtlInterface
    elif ident in (b'XCXI',):
        ctor = LinkObjXCtlToXInterface
    elif ident in (b'VIXC',):
        ctor = LinkObjVIToXCtlInterface
    elif ident in (b'VIXN',):
        ctor = LinkObjVIToXNodeInterface
    elif ident in (b'XVPR',):
        ctor = LinkObjVIToXNodeProjectItemLink
    elif ident in (b'XHPR',):
        ctor = LinkObjHeapToXNodeProjectItemLink
    elif ident in (b'AXVT',):
        ctor = LinkObjActiveXVIToTypeLib
    elif ident in (b'VILB',):
        ctor = LinkObjVIToLib
    elif ident in (b'FPPI',):
        ctor = LinkObjUDClassDDOToUDClassAPILink
    elif ident in (b'DDPI',):
        ctor = LinkObjDDODefaultDataToUDClassAPILink
    elif ident in (b'VRPI',):
        ctor = LinkObjHeapObjToUDClassAPILink
    elif ident in (b'VIPI',):
        ctor = LinkObjVIToUDClassAPILink
    elif ident in (b'RVPI',):
        ctor = LinkObjDataValueRefVIToUDClassAPILink
    elif ident in (b'VIVr',):
        ctor = LinkObjVIToVariableAbsoluteLink
    elif ident in (b'VIVl',):
        ctor = LinkObjVIToVariableRelativeLink
    elif ident in (b'HpVr',):
        ctor = LinkObjHeapToVariableAbsoluteLink
    elif ident in (b'HpVL',):
        ctor = LinkObjHeapToVariableRelativeLink
    elif ident in (b'DSVr',):
        ctor = LinkObjDSToVariableAbsoluteLink
    elif ident in (b'DSVl',):
        ctor = LinkObjDSToVariableRelativeLink
    elif ident in (b'DSDS',) or list_ident in (b'VIDS',) and ident in (b'VIDS',):
        ctor = LinkObjDSToDSLink
    elif ident in (b'DSEF',) or list_ident in (b'VIDS',b'BDHP',) and ident in (b'XFun',):
        ctor = LinkObjDSToExtFuncLink
    elif ident in (b'DSCN',) or list_ident in (b'VIDS',b'BDHP',) and ident in (b'LVSB',):
        ctor = LinkObjDSToCINLink
    elif ident in (b'DSSC',) or list_ident in (b'VIDS',) and ident in (b'SFTB',):
        ctor = LinkObjDSToScriptLink
    elif ident in (b'DSCB',):
        ctor = LinkObjDSToCallByRefLink
    elif ident in (b'DSSV',):
        ctor = LinkObjDSToStaticVILink
    elif ident in (b'VIVI',) or list_ident in (b'LVIN',b'BDHP',) and ident in (b'LVIN',):
        ctor = LinkObjVIToStdVILink
    elif ident in (b'VIPR',) or list_ident in (b'LVIN',) and ident in (b'LVPR',):
        ctor = LinkObjVIToProgRetLink
    elif ident in (b'VIPV',) or list_ident in (b'LVIN',b'BDHP',) and ident in (b'POLY',):
        ctor = LinkObjVIToPolyLink
    elif ident in (b'VICC',) or list_ident in (b'LVCC',b'LVIN',b'BDHP',) and ident in (b'LVCC',b'CCCC',):
        ctor = LinkObjVIToCCLink
    elif ident in (b'BSVR',):
        ctor = LinkObjVIToStaticVILink
    elif ident in (b'VIAV',):
        ctor = LinkObjVIToAdaptiveVILink
    elif ident in (b'H2CC',):
        ctor = LinkObjHeapToCCSymbolLink
    elif ident in (b'IUVI',):
        ctor = LinkObjIUseToVILink
    elif ident in (b'.2TD',):
        ctor = LinkObjNonVINonHeapToTypedefLink
    elif ident in (b'CCLO',):
        ctor = LinkObjCCSymbolLink
    elif ident in (b'HpEx',):
        ctor = LinkObjHeapNamedLink
    elif ident in (b'XFil',):
        ctor = LinkObjFilePathLink
    elif ident in (b'RFil',):
        ctor = LinkObjRCFilePathLink
    elif ident in (b'HpFl',):
        ctor = LinkObjHeapToFileLink
    elif ident in (b'HpFN',):
        ctor = LinkObjHeapToFileNoWarnLink
    elif ident in (b'VIRC',):
        ctor = LinkObjVIToRCFileLink
    elif ident in (b'IUIV',):
        ctor = LinkObjIUseToInstantiationVILink
    elif ident in (b'GUGV',):
        ctor = LinkObjGenIUseToGenVILink
    elif ident in (b'NEXF',):
        ctor = LinkObjNodeToEFLink
    elif ident in (b'HVIR',):
        ctor = LinkObjHeapToVILink
    elif ident in (b'PUPV',):
        ctor = LinkObjPIUseToPolyLink
    elif ident in (b'IUPR',):
        ctor = LinkObjIUseToProgRetLink
    elif ident in (b'SVVI',):
        ctor = LinkObjStaticVIRefToVILink
    elif ident in (b'NCIN',):
        ctor = LinkObjNodeToCINLink
    elif ident in (b'NSCR',):
        ctor = LinkObjNodeToScriptLink
    elif ident in (b'SCVI',):
        ctor = LinkObjStaticCallByRefToVILink
    elif ident in (b'RCFL',):
        ctor = LinkObjHeapToRCFileLink
    elif ident in (b'HpVI',):
        ctor = LinkObjHeapToVINamedLink
    elif ident in (b'H2LD',):
        ctor = LinkObjHeapToLibraryDataLink
    elif ident in (b'MNMS',):
        ctor = LinkObjMSNToMSLink
    elif ident in (b'MSIM',):
        ctor = LinkObjMSToMSImplVILink
    elif ident in (b'CBMS',):
        ctor = LinkObjMSCallByRefToMSLink
    elif ident in (b'MUDF',):
        ctor = LinkObjMathScriptLink
    elif ident in (b'FBIV',):
        ctor = LinkObjFBoxLineToInstantnVILink
    elif ident in (b'OBDR',):
        ctor = LinkObjOMHeapToResource
    elif ident in (b'OVIR',):
        ctor = LinkObjOMVIToResource
    elif ident in (b'OXTR',):
        ctor = LinkObjOMExtResLink
    elif ident in (b'GIVI',):
        ctor = LinkObjGIToAbstractVI
    elif ident in (b'GIAY',):
        ctor = LinkObjGIToAbilityVI
    elif ident in (b'XIPY',):
        ctor = LinkObjXIToPropertyVI
    elif ident in (b'XIMD',):
        ctor = LinkObjXIToMethodVI
    elif ident in (b'LIBR',):
        ctor = LinkObjGInterfaceLink
    elif ident in (b'XINT',):
        ctor = LinkObjXInterfaceLink
    elif ident in (b'LVXC',):
        ctor = LinkObjXCtlInterfaceLink
    elif ident in (b'XNDI',):
        ctor = LinkObjXNodeInterfaceLink
    elif ident in (b'VICI',):
        ctor = LinkObjVIToContainerItemLink
    elif ident in (b'HpCI',):
        ctor = LinkObjHeapToContainerItemLink
    elif ident in (b'CILO',):
        ctor = LinkObjContainerItemLinkObj
    elif ident in (b'XPLO',):
        ctor = LinkObjXNodeProjectItemLinkObj
    elif ident in (b'XNEF',):
        ctor = LinkObjXNodeToExtFuncLink
    elif ident in (b'XNVI',):
        ctor = LinkObjXNodeToVILink
    elif ident in (b'AXDT',):
        ctor = LinkObjActiveXBDToTypeLib
    elif ident in (b'AXTL',):
        ctor = LinkObjActiveXTLibLinkObj
    elif ident in (b'XNXI',):
        ctor = LinkObjXNodeToXInterface
    elif ident in (b'HEIR',):
        ctor = LinkObjUDClassLibInheritsLink
    elif ident in (b'C2vi',):
        ctor = LinkObjUDClassLibToVILink
    elif ident in (b'C2VI',):
        ctor = LinkObjUDClassLibToMemberVILink
    elif ident in (b'C2Pr',):
        ctor = LinkObjUDClassLibToPrivDataCtlLink
    elif ident in (b'HOPI',):
        ctor = LinkObjHeapToUDClassAPILink
    elif ident in (b'DyOM',):
        ctor = LinkObjDynInfoToUDClassAPILink
    elif ident in (b'PNOM',):
        ctor = LinkObjPropNodeItemToUDClassAPILink
    elif ident in (b'DRPI',):
        ctor = LinkObjCreOrDesRefToUDClassAPILink
    elif ident in (b'DOPI',):
        ctor = LinkObjDDOToUDClassAPILink
    elif ident in (b'AP2A',):
        ctor = LinkObjAPIToAPILink
    elif ident in (b'AP2I',):
        ctor = LinkObjAPIToNearestImplVILink
    elif ident in (b'AP2C',):
        ctor = LinkObjAPIToChildAPILink
    elif ident in (b'UDPI',):
        ctor = LinkObjHeapToUDClassAPILink
    elif ident in (b'CMem',):
        ctor = LinkObjMemberVIItem
    elif ident in (b'CLIB',):
        ctor = LinkObjUDClassLibrary
    elif ident in (b'HXNI',):
        ctor = LinkObjHeapToXNodeInterface
    elif ident in (b'GINT',):
        ctor = LinkObjHeapToGInterface
    else:
        raise AttributeError("List {} contains unrecognized class {}".format(list_ident,ident))

    return ctor(vi, blockref, list_ident, ident, po)
