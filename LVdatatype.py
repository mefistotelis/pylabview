# -*- coding: utf-8 -*-

""" LabView RSRC file format connectors.

    Virtual Connectors and Terminal Points are stored inside VCTP block.
"""

# Copyright (C) 2013 Jessica Creighton <jcreigh@femtobit.org>
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
from LVblock import *
import LVclasses
import LVheap
import LVdatatyperef
from LVdatatyperef import REFNUM_TYPE


class TD_MAIN_TYPE(enum.IntEnum):
    Number = 0x0	# INT/DBL/complex/...
    Unit = 0x1		# INT+Format: Enum/Units
    Bool = 0x2		# only Boolean
    Blob = 0x3		# String/Path/...
    Array = 0x4		# Array
    Cluster = 0x5	# Struct (hard code [Timestamp] or flexibl)
    Block = 0x6		# Data divided into blocks
    Ref = 0x7		# Pointers
    NumberPointer = 0x8	# INT+Format: Enum/Units Pointer
    Terminal = 0xF	# like Cluser+Flags/Typdef
    # Custom / internal to this parser / not official
    Void = 0x100	# 0 is used for numbers
    Unknown = -1
    EnumValue = -2		# Entry for Enum


class TD_FULL_TYPE(enum.IntEnum):
    """ known types of connectors

    All types from LabVIEW 2014 are there.
    """
    Void =			0x00

    NumInt8 =		0x01 # Integer with signed 1 byte data
    NumInt16 =		0x02 # Integer with signed 2 byte data
    NumInt32 =		0x03 # Integer with signed 4 byte data
    NumInt64 =		0x04 # Integer with signed 8 byte data
    NumUInt8 =		0x05 # Integer with unsigned 1 byte data
    NumUInt16 =		0x06 # Integer with unsigned 2 byte data
    NumUInt32 =		0x07 # Integer with unsigned 4 byte data
    NumUInt64 =		0x08 # Integer with unsigned 8 byte data
    NumFloat32 =	0x09 # floating point with single precision 4 byte data
    NumFloat64 =	0x0A # floating point with double precision 8 byte data
    NumFloatExt =	0x0B # floating point with extended data
    NumComplex64 =	0x0C # complex floating point with 8 byte data
    NumComplex128 =	0x0D # complex floating point with 16 byte data
    NumComplexExt =	0x0E # complex floating point with extended data

    UnitUInt8 =		0x15
    UnitUInt16 =	0x16
    UnitUInt32 =	0x17
    UnitFloat32 =	0x19
    UnitFloat64 =	0x1A
    UnitFloatExt =	0x1B
    UnitComplex64 =	0x1C
    UnitComplex128 = 0x1D
    UnitComplexExt = 0x1E

    BooleanU16 =	0x20
    Boolean =		0x21

    String =		0x30
    String2 =		0x31
    Path =			0x32
    Picture =		0x33
    CString =		0x34
    PasString =		0x35
    Tag =			0x37
    SubString =		0x3F

    Array =			0x40
    ArrayDataPtr =	0x41
    SubArray =		0x4F

    Cluster =		0x50
    LVVariant =		0x53
    MeasureData =	0x54
    ComplexFixedPt = 0x5E
    FixedPoint =	0x5F

    Block =			0x60
    TypeBlock =		0x61
    VoidBlock =		0x62
    AlignedBlock =	0x63
    RepeatedBlock =	0x64
    AlignmntMarker = 0x65

    Refnum =		0x70

    Ptr =			0x80
    PtrTo =			0x83
    ExtData =		0x84

    ArrayInterfc =	0xA0
    InterfcToData =	0xA1

    Function =		0xF0
    TypeDef =		0xF1
    PolyVI =		0xF2

    # Not official
    Unknown = -1
    EnumValue =	-2


class MEASURE_DATA_FLAVOR(enum.IntEnum):
    """ Flavor of data within Measure Data Type

    Used for types which do not describe the data kind well enough by themselves,
    like MeasureData
    """
    OldFloat64Waveform = 1
    Int16Waveform =		2
    Float64Waveform =	3
    Float32Waveform =	5
    TimeStamp =			6
    Digitaldata =		7
    DigitalWaveform = 	8
    Dynamicdata =		9
    FloatExtWaveform =	10
    UInt8Waveform =		11
    UInt16Waveform =	12
    UInt32Waveform =	13
    Int8Waveform =		14
    Int32Waveform =		15
    Complex64Waveform =	16
    Complex128Waveform = 17
    ComplexExtWaveform = 18
    Int64Waveform =		19
    UInt64Waveform =	20


class CONNECTOR_FLAGS(enum.Enum):
    """ Connector flags
    """
    Bit0 = 1 << 0	# unknown
    Bit1 = 1 << 1	# unknown
    Bit2 = 1 << 2	# unknown
    Bit3 = 1 << 3	# unknown
    Bit4 = 1 << 4	# unknown
    Bit5 = 1 << 5	# unknown
    HasLabel = 1 << 6	# After connector data, there is a string label stored
    Bit7 = 1 << 7	# unknown


class TAG_TYPE(enum.Enum):
    """ Type of tag
    """
    Unknown0 = 0
    Unknown1 = 1
    Unknown2 = 2
    Unknown3 = 3
    Unknown4 = 4
    UserDefined = 5


class EXT_DATA_TYPE_KIND(enum.Enum):
    """ Kind of data inside Ext Data type
    """
    Unknown0 = 0
    OleVariant = 1
    IDispatch = 2
    IUnknown = 3


class NUMBER_UNIT(enum.IntEnum):
    Radians =	0
    Steradians =	1
    Seconds =	2
    Meters =	3
    Kilograms =	4
    Amperes =	5
    Kelvins =	6
    Moles =	7
    Candelas =	8
    Invalid =	9


class LV_INTERNAL_TD_NAMES(LVheap.ENUM_TAGS):
    """ Names of types from LV

    This maps the names of types this tool uses to names LV uses internally.
    We may want to keep LV names when exporting data. All values from
    TD_FULL_TYPE should be mapped here, even if the names are identical.
    """
    Void =	TD_FULL_TYPE.Void
    I8 =	TD_FULL_TYPE.NumInt8
    I16 =	TD_FULL_TYPE.NumInt16
    I32 =	TD_FULL_TYPE.NumInt32
    I64 =	TD_FULL_TYPE.NumInt64
    U8 =	TD_FULL_TYPE.NumUInt8
    U16 =	TD_FULL_TYPE.NumUInt16
    U32 =	TD_FULL_TYPE.NumUInt32
    U64 =	TD_FULL_TYPE.NumUInt64
    SGL =	TD_FULL_TYPE.NumFloat32
    DBL =	TD_FULL_TYPE.NumFloat64
    EXT =	TD_FULL_TYPE.NumFloatExt
    CSG =	TD_FULL_TYPE.NumComplex64
    CDB =	TD_FULL_TYPE.NumComplex128
    CXT =	TD_FULL_TYPE.NumComplexExt
    EB =	TD_FULL_TYPE.UnitUInt8
    EW =	TD_FULL_TYPE.UnitUInt16
    EL =	TD_FULL_TYPE.UnitUInt32
    UnitFloat32 =	TD_FULL_TYPE.UnitFloat32
    UnitFloat64 =	TD_FULL_TYPE.UnitFloat64
    UnitFloatExt =	TD_FULL_TYPE.UnitFloatExt
    UnitComplex64 =	TD_FULL_TYPE.UnitComplex64
    UnitComplex128 = TD_FULL_TYPE.UnitComplex128
    UnitComplexExt = TD_FULL_TYPE.UnitComplexExt
    BooleanU16 =	TD_FULL_TYPE.BooleanU16
    Boolean =	TD_FULL_TYPE.Boolean
    String =	TD_FULL_TYPE.String
    String2 =	TD_FULL_TYPE.String2
    Path =		TD_FULL_TYPE.Path
    Picture =	TD_FULL_TYPE.Picture
    CString =	TD_FULL_TYPE.CString
    PasString =	TD_FULL_TYPE.PasString
    Tag =		TD_FULL_TYPE.Tag
    SubString =	TD_FULL_TYPE.SubString
    Array =		TD_FULL_TYPE.Array
    ArrayDataPtr =	TD_FULL_TYPE.ArrayDataPtr
    SubArray =	TD_FULL_TYPE.SubArray
    Cluster =	TD_FULL_TYPE.Cluster
    LvVariant =	TD_FULL_TYPE.LVVariant
    MeasureData =	TD_FULL_TYPE.MeasureData
    ComplexFixedPt = TD_FULL_TYPE.ComplexFixedPt
    FixedPoint =	TD_FULL_TYPE.FixedPoint
    Block =		TD_FULL_TYPE.Block
    TypeBlock =	TD_FULL_TYPE.TypeBlock
    VoidBlock =	TD_FULL_TYPE.VoidBlock
    AlignedBlock =	TD_FULL_TYPE.AlignedBlock
    RepeatedBlock =	TD_FULL_TYPE.RepeatedBlock
    AlignmntMarker = TD_FULL_TYPE.AlignmntMarker
    Refnum =	TD_FULL_TYPE.Refnum
    Ptr =		TD_FULL_TYPE.Ptr
    PtrTo =		TD_FULL_TYPE.PtrTo
    ExtData =	TD_FULL_TYPE.ExtData
    ArrayInterfc =	TD_FULL_TYPE.ArrayInterfc
    InterfcToData =	TD_FULL_TYPE.InterfcToData
    Function =	TD_FULL_TYPE.Function
    TypeDef =	TD_FULL_TYPE.TypeDef
    PolyVI =	TD_FULL_TYPE.PolyVI
    #Version = TD_FULL_TYPE.Void
    #DAQChannel = TD_FULL_TYPE.Void


class LV_INTERNAL_MEAS_FLAVOR_NAMES(LVheap.ENUM_TAGS):
    """ Names of MeasureData flavors from LV

    This maps the names of MeasureData flavors this tool uses to names LV uses
    internally. All values from MEASURE_DATA_FLAVOR should be mapped here.
    """
    WDT =			MEASURE_DATA_FLAVOR.OldFloat64Waveform
    I16Waveform =	MEASURE_DATA_FLAVOR.Int16Waveform
    DBLWaveform =	MEASURE_DATA_FLAVOR.Float64Waveform
    SGLWaveform =	MEASURE_DATA_FLAVOR.Float32Waveform
    Timestamp =		MEASURE_DATA_FLAVOR.TimeStamp
    DigitalData =	MEASURE_DATA_FLAVOR.Digitaldata
    DigitalWaveform = MEASURE_DATA_FLAVOR.DigitalWaveform
    DynamicData =	MEASURE_DATA_FLAVOR.Dynamicdata
    EXTWaveform =	MEASURE_DATA_FLAVOR.FloatExtWaveform
    U8Waveform =	MEASURE_DATA_FLAVOR.UInt8Waveform
    U16Waveform =	MEASURE_DATA_FLAVOR.UInt16Waveform
    U32Waveform =	MEASURE_DATA_FLAVOR.UInt32Waveform
    I8Waveform =	MEASURE_DATA_FLAVOR.Int8Waveform
    I32Waveform =	MEASURE_DATA_FLAVOR.Int32Waveform
    CSGWaveform =	MEASURE_DATA_FLAVOR.Complex64Waveform
    CDBWaveform =	MEASURE_DATA_FLAVOR.Complex128Waveform
    CXTWaveform =	MEASURE_DATA_FLAVOR.ComplexExtWaveform
    I64Waveform =	MEASURE_DATA_FLAVOR.Int64Waveform
    U64Waveform =	MEASURE_DATA_FLAVOR.UInt64Waveform


class TDObject:

    def __init__(self, vi, idx, obj_flags, obj_type, po):
        """ Creates new Connector object, capable of handling generic Connector data.
        """
        self.vi = vi
        self.po = po
        self.index = idx
        self.oflags = obj_flags
        self.otype = obj_type
        self.clients = []
        # Dependencies to other types are either indexes in Consolidated List, or locally stored topTypeList
        self.topTypeList = None
        self.label = None
        self.size = None
        self.raw_data = None
        # Whether RAW data has been updated and RSRC parsing is required to update properties
        self.raw_data_updated = False
        # Whether any properties have been updated and preparation of new RAW data is required
        self.parsed_data_updated = False

    def initWithRSRC(self, bldata, obj_len, typeList=None):
        """ Early part of connector loading from RSRC file

        At the point it is executed, other sections are inaccessible.
        """
        self.topTypeList = typeList
        self.size = obj_len
        self.raw_data = bldata.read(obj_len)
        self.raw_data_updated = True

    def initWithXMLInlineStart(self, conn_elem):
        """ Early part of connector loading from XML file using Inline formats

        That is simply a common part used in all overloaded initWithXML(),
        separated only to avoid code duplication.
        """
        self.label = None
        label_text = conn_elem.get("Label")
        if label_text is not None:
            self.label = label_text.encode(self.vi.textEncoding)
        self.parsed_data_updated = True

    def initWithXML(self, conn_elem):
        """ Early part of connector loading from XML file

        At the point it is executed, other sections are inaccessible.
        To be overriden by child classes which want to load more properties from XML.
        """
        fmt = conn_elem.get("Format")
        # TODO the inline block belongs to inheriting classes, not here - move
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)

            self.updateData(avoid_recompute=True)

        elif fmt == "bin":# Format="bin" - the content is stored separately as raw binary data
            if (self.po.verbose > 2):
                print("{:s}: For Connector {}, reading BIN file '{}'"\
                  .format(self.vi.src_fname,self.index,conn_elem.get("File")))
            # If there is label in binary data, set our label property to non-None value
            self.label = None
            if (self.oflags & CONNECTOR_FLAGS.HasLabel.value) != 0:
                self.label = b""

            bin_path = os.path.dirname(self.vi.src_fname)
            if len(bin_path) > 0:
                bin_fname = bin_path + '/' + conn_elem.get("File")
            else:
                bin_fname = conn_elem.get("File")
            with open(bin_fname, "rb") as bin_fh:
                data_buf = bin_fh.read()
            data_head = int(len(data_buf)+4).to_bytes(2, byteorder='big')
            data_head += int(self.oflags).to_bytes(1, byteorder='big')
            data_head += int(self.otype).to_bytes(1, byteorder='big')
            self.setData(data_head+data_buf)
            self.parsed_data_updated = False
        else:
            raise NotImplementedError("Unsupported Connector {} Format '{}'.".format(self.index,fmt))
        pass

    def initWithXMLLate(self):
        """ Late part of TD loading from XML file

        Can access some basic data from other blocks and sections.
        Useful only if properties needs an update after other blocks are accessible.
        """
        pass

    @staticmethod
    def parseRSRCDataHeader(bldata):
        obj_len = readVariableSizeFieldU2p2(bldata)
        obj_flags = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        obj_type = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        return obj_type, obj_flags, obj_len

    def parseRSRCData(self, bldata):
        """ Implements final stage of setting connector properties from RSRC file

        Can use other connectors and other blocks.
        """
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        if (self.po.verbose > 2):
            print("{:s}: TD {:d} type 0x{:02x} data format isn't known; leaving raw only"\
              .format(self.vi.src_fname,self.index,self.otype))

        self.parseRSRCDataFinish(bldata)

    @staticmethod
    def validLabelLength(whole_data, i):
        # Strip padding at the end
        #whole_data = whole_data.rstrip(b'\0')
        ending_zeros = 0
        if whole_data[-1] == 0:
            ending_zeros += 1
        if ending_zeros > 0:
            whole_data = whole_data[:-ending_zeros]
        # Check if this position can be a label start
        label_len = int.from_bytes(whole_data[i:i+1], byteorder='big', signed=False)
        if (len(whole_data)-i == label_len+1) and all((bt in b'\r\n\t') or (bt >= 32) for bt in whole_data[i+1:]):
            return label_len
        return 0

    def parseRSRCDataFinish(self, bldata):
        """ Does generic part of RSRC connector parsing and marks the parse as finished

        Really, it mostly implements setting connector label from RSRC file.
        The label behaves in the same way for every connector type, so this function
        is really a type-independent part of parseRSRCData().
        """
        if (self.oflags & CONNECTOR_FLAGS.HasLabel.value) != 0:
            min_pos = bldata.tell() # We receive the file with pos set at minimal - the label can't start before it
            # The data should be smaller than 256 bytes; but it is still wise to make some restriction on it
            whole_data = bldata.read(1024*1024)
            # Find a proper position to read the label; try the current position first (if the data after current is not beyond 255)
            for i in range(max(len(whole_data)-256,0), len(whole_data)):
                label_len = TDObject.validLabelLength(whole_data, i)
                if label_len > 0:
                    self.label = whole_data[i+1:i+label_len+1]
                    break
            if self.label is None:
                if (self.po.verbose > 0):
                    eprint("{:s}: Warning: TD {:d} type 0x{:02x} label text not found"\
                      .format(self.vi.src_fname, self.index, self.otype))
                self.label = b""
            elif i > 0:
                if (self.po.verbose > 0):
                    eprint("{:s}: Warning: TD {:d} type 0x{:02x} has label not immediatelly following data"\
                      .format(self.vi.src_fname, self.index, self.otype))
        self.raw_data_updated = False

    def parseXMLData(self):
        """ Implements final stage of setting connector properties from XML

        Can use other connectors and other blocks.
        """
        self.parsed_data_updated = False

    def parseData(self):
        """ Parse data of specific section and place it as Connector properties
        """
        if self.needParseData():
            if self.raw_data_updated:
                bldata = self.getData()
                self.parseRSRCData(bldata)
            elif self.parsed_data_updated:
                self.parseXMLData()
            elif self.vi.dataSource == "rsrc":
                bldata = self.getData()
                self.parseRSRCData(bldata)
            elif self.vi.dataSource == "xml":
                self.parseXMLData()
            for i, client in enumerate(self.clients):
                if client.index != -1: # this is how we mark nested client
                    continue
                conn_obj = client.nested
                conn_obj.parseData()
        pass

    def needParseData(self):
        """ Returns if the connector did not had its data parsed yet

            After a call to parseData(), or after filling the data manually, this should
            return True. Otherwise, False.
        """
        return self.raw_data_updated or self.parsed_data_updated

    def prepareRSRCData(self, avoid_recompute=False):
        """ Returns part of the connector data re-created from properties.

        To be overloaded in classes for specific connector types.
        """
        if self.raw_data:
            data_buf = self.raw_data[4:]
        else:
            data_buf = b''

        # Remove label from the end - use the algorithm from parseRSRCDataFinish() for consistency
        if (self.oflags & CONNECTOR_FLAGS.HasLabel.value) != 0:
            whole_data = data_buf
            # Find a proper position to read the label; try the current position first (if the data after current is not beyond 255)
            for i in range(max(len(whole_data)-256,0), len(whole_data)):
                label_len = TDObject.validLabelLength(whole_data, i)
                if label_len > 0:
                    data_buf = data_buf[:i]
                    break
        # Done - got the data part only
        return data_buf

    def prepareRSRCDataFinish(self):
        data_buf = b''

        if self.label is not None:
            self.oflags |= CONNECTOR_FLAGS.HasLabel.value
            if len(self.label) > 255:
                self.label = self.label[:255]
            data_buf += int(len(self.label)).to_bytes(1, byteorder='big')
            data_buf += self.label
        else:
            self.oflags &= ~CONNECTOR_FLAGS.HasLabel.value

        if len(data_buf) % 2 > 0:
            padding_len = 2 - (len(data_buf) % 2)
            data_buf += (b'\0' * padding_len)

        return data_buf

    def expectedRSRCSize(self):
        """ Returns expected RAW data size of this connector.

        The expected size includes header and label size - it is the size of whole data.
        """
        if self.raw_data is not None:
            exp_whole_len = len(self.raw_data)
        else:
            exp_whole_len = 4
        return exp_whole_len

    def updateData(self, avoid_recompute=False):

        if avoid_recompute and self.raw_data_updated:
            return # If we have strong raw data, and new one will be weak, then leave the strong buffer

        data_buf = self.prepareRSRCData(avoid_recompute=avoid_recompute)
        data_buf += self.prepareRSRCDataFinish()

        data_head = int(len(data_buf)+4).to_bytes(2, byteorder='big')
        data_head += int(self.oflags).to_bytes(1, byteorder='big')
        data_head += int(self.otype).to_bytes(1, byteorder='big')

        self.setData(data_head+data_buf, incomplete=avoid_recompute)

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        # TODO the inline block belongs to inheriting classes, not here - move
        if self.size <= 4:
            # Connector stores no additional data
            conn_elem.set("Format", "inline")
        else:
            if self.index >= 0:
                part_fname = "{:s}_{:04d}.{:s}".format(fname_base,self.index,"bin")
            else:
                part_fname = "{:s}.{:s}".format(fname_base,"bin")
            if (self.po.verbose > 2):
                print("{:s}: For Connector {}, writing BIN file '{}'"\
                  .format(self.vi.src_fname,self.index,os.path.basename(part_fname)))
            bldata = self.getData()
            bldata.read(4) # The data includes 4-byte header
            with open(part_fname, "wb") as part_fd:
                part_fd.write(bldata.read())

            conn_elem.set("Format", "bin")
            conn_elem.set("File", os.path.basename(part_fname))

    def exportXMLFinish(self, conn_elem):
        # Now fat chunk of code for handling connector label
        if self.label is not None:
            self.oflags |= CONNECTOR_FLAGS.HasLabel.value
        else:
            self.oflags &= ~CONNECTOR_FLAGS.HasLabel.value
        # While exporting flags and label, mind the export format set by exportXML()
        if conn_elem.get("Format") == "bin":
            # For binary format, export only HasLabel flag instead of the actual label; label is in binary data
            exportXMLBitfields(CONNECTOR_FLAGS, conn_elem, self.oflags)
        else:
            # For parsed formats, export "Label" property, and get rid of the flag; existence of the "Label" acts as flag
            exportXMLBitfields(CONNECTOR_FLAGS, conn_elem, self.oflags, \
              skip_mask=CONNECTOR_FLAGS.HasLabel.value)
            if self.label is not None:
                label_text = self.label.decode(self.vi.textEncoding)
                conn_elem.set("Label", "{:s}".format(label_text))
        pass

    def getData(self):
        bldata = BytesIO(self.raw_data)
        return bldata

    def setData(self, data_buf, incomplete=False):
        self.raw_data = data_buf
        self.size = len(self.raw_data)
        if not incomplete:
            self.raw_data_updated = True

    def checkSanity(self):
        ret = True
        return ret

    def mainType(self):
        if self.otype == 0x00:
            # Special case; if lower bits are non-zero, it is treated as int
            # But if the whole value is 0, then its just void
            return TD_MAIN_TYPE.Void
        elif self.otype < 0:
            # Types internal to this parser - mapped without bitshift
            return TD_MAIN_TYPE(self.otype)
        else:
            return TD_MAIN_TYPE(self.otype >> 4)

    def fullType(self):
        if self.otype not in set(item.value for item in TD_FULL_TYPE):
            return self.otype
        return TD_FULL_TYPE(self.otype)

    def isNumber(self):
        return ( \
          (self.mainType() == TD_MAIN_TYPE.Number) or \
          (self.mainType() == TD_MAIN_TYPE.Unit) or \
          (self.fullType() == TD_FULL_TYPE.FixedPoint));

    def isString(self):
        return ( \
          (self.fullType() == TD_FULL_TYPE.String));
        # looks like these are not counted as strings?
        #  (self.fullType() == TD_FULL_TYPE.CString) or \
        #  (self.fullType() == TD_FULL_TYPE.PasString));

    def isPath(self):
        return ( \
          (self.fullType() == TD_FULL_TYPE.Path));

    def hasClients(self):
        return (len(self.clients) > 0)

    def clientsEnumerate(self):
        if self.topTypeList is not None:
            typeList = self.topTypeList
        else:
            VCTP = self.vi.get_or_raise('VCTP')
            typeList = VCTP.getContent()
        out_enum = []
        for i, client in enumerate(self.clients):
            if client.index == -1: # This is how we mark nested client
                conn_obj = client.nested
            else:
                conn_obj = typeList[client.index].nested
            out_enum.append( (i, client.index, conn_obj, client.flags, ) )
        return out_enum

    def getClientConnectorsByType(self):
        self.parseData() # Make sure the block is parsed
        out_lists = { 'number': [], 'path': [], 'string': [], 'compound': [], 'other': [] }
        for cli_idx, conn_idx, conn_obj, conn_flags in self.clientsEnumerate():
            # We will need a list of clients, so might as well parse the connector now
            conn_obj.parseData()
            if not conn_obj.checkSanity():
                if (self.po.verbose > 0):
                    eprint("{:s}: Warning: TD {:d} type 0x{:02x} sanity check failed!"\
                      .format(self.vi.src_fname,conn_obj.index,conn_obj.otype))
            # Add connectors of this Terminal to list
            if conn_obj.isNumber():
                out_lists['number'].append(conn_obj)
            elif conn_obj.isPath():
                out_lists['path'].append(conn_obj)
            elif conn_obj.isString():
                out_lists['string'].append(conn_obj)
            elif conn_obj.hasClients():
                out_lists['compound'].append(conn_obj)
            else:
                out_lists['other'].append(conn_obj)
            if (self.po.verbose > 2):
                keys = list(out_lists)
                print("enumerating: {}.{} idx={} flags={:09x} type={} connectors: {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d}"\
                      .format(self.index, cli_idx, conn_idx,  conn_flags,\
                        conn_obj.fullType().name if isinstance(conn_obj.fullType(), enum.IntEnum) else conn_obj.fullType(),\
                        keys[0],len(out_lists[keys[0]]),\
                        keys[1],len(out_lists[keys[1]]),\
                        keys[2],len(out_lists[keys[2]]),\
                        keys[3],len(out_lists[keys[3]]),\
                        keys[4],len(out_lists[keys[4]]),\
                      ))
            # Add sub-connectors the terminals within this connector
            if conn_obj.hasClients():
                sub_lists = conn_obj.getClientConnectorsByType()
                for k in out_lists:
                    out_lists[k].extend(sub_lists[k])
        return out_lists

    def __repr__(self):
        d = self.__dict__.copy()
        del d['vi']
        del d['po']
        del d['parsed_data_updated']
        del d['raw_data_updated']
        del d['raw_data']
        del d['size']
        from pprint import pformat
        return type(self).__name__ + pformat(d, indent=0, compact=True, width=512)


class TDObjectVoid(TDObject):
    """ Connector with Void data
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)
        # And that is it, no other data expected
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()
        # Connector stores no additional data
        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


class TDObjectBool(TDObjectVoid):
    """ Connector with Boolean data

    Stores no additional data, so handling is identical to Void connector.
    """
    pass


class TDObjectLVVariant(TDObjectVoid):
    """ Connector with data supporting multiple types(variant type)

    Stores no additional data, so handling is identical to Void connector.
    """
    pass


class TDObjectNumber(TDObject):
    """ Connector with single number as data

        The number can be a clear math value, but also can be physical value with
        a specific unit, or may come from an enum with each value having a label.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.values = []
        self.prop1 = None
        self.padding1 = b''

    def parseRSRCEnumAttr(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        self.values = [SimpleNamespace() for _ in range(count)]
        whole_len = 0
        for i in range(count):
            label_len = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.values[i].label = bldata.read(label_len)
            self.values[i].intval1 = None
            self.values[i].intval2 = None
            whole_len += label_len + 1
        if (whole_len % 2) != 0:
            self.padding1 = bldata.read(1)
        pass

    def parseRSRCUnitsAttr(self, bldata):
        count = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # Create _separate_ empty namespace for each connector
        self.values = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            intval1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            intval2 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            self.values[i].label = "0x{:02X}:0x{:02X}".format(intval1,intval2)
            self.values[i].intval1 = intval1
            self.values[i].intval2 = intval2
        pass

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)
        self.padding1 = b''
        self.values = []

        if self.isEnum():
            self.parseRSRCEnumAttr(bldata)

        if self.isPhys():
            self.parseRSRCUnitsAttr(bldata)

        self.prop1 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        # No more data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCEnumAttr(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.values)).to_bytes(2, byteorder='big')
        for value in self.values:
            data_buf += int(len(value.label)).to_bytes(1, byteorder='big')
            data_buf += value.label
        if len(data_buf) % 2 > 0:
            padding_len = 2 - (len(data_buf) % 2)
            data_buf += (b'\0' * padding_len)
        return data_buf

    def prepareRSRCUnitsAttr(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.values)).to_bytes(2, byteorder='big')
        for i, value in enumerate(self.values):
            data_buf += int(value.intval1).to_bytes(2, byteorder='big')
            data_buf += int(value.intval2).to_bytes(2, byteorder='big')
            if (self.po.verbose > 2):
                print("{:s}: TD {:d} type 0x{:02x} Units Attr {} are 0x{:02X} 0x{:02X}"\
                  .format(self.vi.src_fname,self.index,self.otype,i,value.intval1,value.intval2))
        return data_buf

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''

        if self.isEnum():
            data_buf += self.prepareRSRCEnumAttr(avoid_recompute=avoid_recompute)

        if self.isPhys():
            data_buf += self.prepareRSRCUnitsAttr(avoid_recompute=avoid_recompute)

        data_buf += int(self.prop1).to_bytes(1, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        if self.isEnum():
            exp_whole_len += 2 + sum((1+len(v.label)) for v in self.values)
            if exp_whole_len % 2 > 0:
                exp_whole_len += 2 - (exp_whole_len % 2)
        if self.isPhys():
            exp_whole_len = 2 + (2+2) * len(self.values)
        exp_whole_len += 1
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXMLEnumAttr(self, conn_elem):
        for subelem in conn_elem:
            if (subelem.tag == "Value"):
                i = int(subelem.get("Index"), 0)
                value = SimpleNamespace()
                label_str = subelem.get("EnumLabel")
                value.label = label_str.encode(self.vi.textEncoding)
                value.intval1 = None
                value.intval2 = None
                # Grow the list if needed (the values may be in wrong order)
                if i >= len(self.values):
                    self.values.extend([None] * (i - len(self.values) + 1))
                self.values[i] = value
            else:
                raise AttributeError("Connector contains unexpected tag")
        pass

    def initWithXMLUnitsAttr(self, conn_elem):
        for subelem in conn_elem:
            if (subelem.tag == "Value"):
                i = int(subelem.get("Index"), 0)
                value = SimpleNamespace()
                value.intval1 = int(subelem.get("UnitVal1"), 0)
                value.intval2 = int(subelem.get("UnitVal2"), 0)
                value.label = "0x{:02X}:0x{:02X}".format(value.intval1,value.intval2)
                if (self.po.verbose > 2):
                    print("{:s}: TD {:d} type 0x{:02x} Units Attr {} are 0x{:02X} 0x{:02X}"\
                      .format(self.vi.src_fname,self.index,self.otype,i,value.intval1,value.intval2))
                # Grow the list if needed (the values may be in wrong order)
                if i >= len(self.values):
                    self.values.extend([None] * (i - len(self.values) + 1))
                self.values[i] = value
            else:
                raise AttributeError("Connector contains unexpected tag")
        pass

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.prop1 = int(conn_elem.get("Prop1"), 0)
            self.padding1 = b''
            self.values = []

            if self.isEnum():
                self.initWithXMLEnumAttr(conn_elem)
            if self.isPhys():
                self.initWithXMLUnitsAttr(conn_elem)

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXMLEnumAttr(self, conn_elem, fname_base):
        for i, value in enumerate(self.values):
            subelem = ET.SubElement(conn_elem,"Value")

            subelem.set("Index", "{:d}".format(i))
            label_str = value.label.decode(self.vi.textEncoding)
            subelem.set("EnumLabel", label_str)
        pass

    def exportXMLUnitsAttr(self, conn_elem, fname_base):
        for i, value in enumerate(self.values):
            subelem = ET.SubElement(conn_elem,"Value")

            subelem.set("Index", "{:d}".format(i))
            subelem.set("UnitVal1", "{:d}".format(value.intval1))
            subelem.set("UnitVal2", "{:d}".format(value.intval2))
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()
        conn_elem.set("Prop1", "{:d}".format(self.prop1))
        if self.isEnum():
            self.exportXMLEnumAttr(conn_elem, fname_base)
        if self.isPhys():
            self.exportXMLUnitsAttr(conn_elem, fname_base)
        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if (self.prop1 & ~1) != 0: # 0 or 1
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02X} property1 {:d}, expected 1 bit value"\
                  .format(self.vi.src_fname,self.index,self.otype,self.prop1))
            ret = False
        if (self.isEnum() or self.isPhys()):
            if len(self.values) < 1:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TD {:d} type 0x{:02X} has empty values list"\
                      .format(self.vi.src_fname,self.index,self.otype))
                ret = False
        if len(self.padding1) > 0 and (self.padding1 != b'\0'):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02X} padding1 {}, expected zeros"\
                  .format(self.vi.src_fname,self.index,self.otype,self.padding1))
            ret = False
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02X} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret

    def isEnum(self):
        return self.fullType() in [
          TD_FULL_TYPE.UnitUInt8,
          TD_FULL_TYPE.UnitUInt16,
          TD_FULL_TYPE.UnitUInt32,
        ]

    def isPhys(self):
        return self.fullType() in [
          TD_FULL_TYPE.UnitFloat32,
          TD_FULL_TYPE.UnitFloat64,
          TD_FULL_TYPE.UnitFloatExt,
          TD_FULL_TYPE.UnitComplex64,
          TD_FULL_TYPE.UnitComplex128,
          TD_FULL_TYPE.UnitComplexExt,
        ]


class TDObjectCString(TDObjectVoid):
    """ Connector with C String data

    Stores no additional data, so handling is identical to Void connector.
    """
    pass


class TDObjectPasString(TDObjectVoid):
    """ Connector with Pascal String data

    Stores no additional data, so handling is identical to Void connector.
    """
    pass


class TDObjectTag(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.prop1 = 0
        self.tagType = 0
        self.variobj = None
        self.ident = None

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.prop1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        self.tagType = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        if isGreaterOrEqVersion(ver, 8,2,1) and \
          (isSmallerVersion(ver, 8,2,2) or isGreaterOrEqVersion(ver, 8,5,1)):
            obj = LVclasses.LVVariant(0, self.vi, self.po)
            self.variobj = obj
            obj.parseRSRCData(bldata)

        if (self.tagType == TAG_TYPE.UserDefined.value) and isGreaterOrEqVersion(ver, 8,1,1):
            # The data start with a string, 1-byte length, padded to mul of 2
            strlen = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
            self.ident = bldata.read(strlen)
            if ((strlen+1) % 2) > 0:
                bldata.read(1) # Padding byte

        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = b''
        data_buf += int(self.prop1).to_bytes(4, byteorder='big')
        data_buf += int(self.tagType).to_bytes(2, byteorder='big')

        if isGreaterOrEqVersion(ver, 8,2,1) and \
          (isSmallerVersion(ver, 8,2,2) or isGreaterOrEqVersion(ver, 8,5,1)):
            data_buf += self.variobj.prepareRSRCData(avoid_recompute=avoid_recompute)

        if (self.tagType == TAG_TYPE.UserDefined.value) and isGreaterOrEqVersion(ver, 8,1,1):
            strlen = len(self.ident)
            data_buf += int(strlen).to_bytes(1, byteorder='big')
            data_buf += self.ident
            if ((strlen+1) % 2) > 0:
                data_buf += b'\0' # padding

        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 4
        exp_whole_len += 4 + 2
        if isGreaterOrEqVersion(ver, 8,2,1) and \
          (isSmallerVersion(ver, 8,2,2) or isGreaterOrEqVersion(ver, 8,5,1)):
            exp_whole_len += self.variobj.expectedRSRCSize()
        if (self.tagType == TAG_TYPE.UserDefined.value) and isGreaterOrEqVersion(ver, 8,1,1):
            strlen = len(self.ident)
            if ((strlen+1) % 2) > 0:
                strlen += 1
            exp_whole_len += 1+strlen
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)

            self.prop1 = int(conn_elem.get("Prop1"), 0)
            self.tagType = valFromEnumOrIntString(TAG_TYPE, conn_elem.get("TagType"))
            identStr = conn_elem.get("Ident")
            if identStr is not None:
                self.ident = identStr.encode(self.vi.textEncoding)
            self.variobj = None

            for subelem in conn_elem:
                if (subelem.tag == "LVVariant"):
                    i = int(subelem.get("Index"), 0)
                    obj = LVclasses.LVVariant(i, self.vi, self.po)
                    obj.initWithXML(subelem)
                    self.variobj = obj
                else:
                    raise AttributeError("Connector contains unexpected tag")

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        if self.variobj is not None:
            self.variobj.initWithXMLLate()
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        conn_elem.set("Prop1", "0x{:X}".format(self.prop1))
        conn_elem.set("TagType", stringFromValEnumOrInt(TAG_TYPE, self.tagType))
        if self.ident is not None:
            conn_elem.set("Ident", self.ident.decode(self.vi.textEncoding))

        if self.variobj is not None:
            obj = self.variobj
            i = 0
            subelem = ET.SubElement(conn_elem,"LVObject") # Export function from the object may overwrite the tag

            subelem.set("Index", "{:d}".format(i))

            if self.index >= 0:
                part_fname = "{:s}_{:04d}_lvo{:02d}".format(fname_base,self.index,i)
            else:
                part_fname = "{:s}_lvo{:02d}".format(fname_base,i)
            obj.exportXML(subelem, part_fname)

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if self.prop1 != 0xFFFFFFFF:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} property1 0x{:x}, expected 0x{:x}"\
                  .format(self.vi.src_fname,self.index,self.otype,self.prop1,0xFFFFFFFF))
            ret = False
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


class TDObjectBlob(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.prop1 = None

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.prop1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False) # size of block/blob
        # No more known data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.prop1).to_bytes(4, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 4
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.prop1 = int(conn_elem.get("Prop1"), 0)

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()
        conn_elem.set("Prop1", "0x{:X}".format(self.prop1))
        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if self.otype not in (TD_FULL_TYPE.PolyVI, TD_FULL_TYPE.Block,):
            if self.prop1 != 0xFFFFFFFF:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TD {:d} type 0x{:02x} property1 0x{:x}, expected 0x{:x}"\
                      .format(self.vi.src_fname,self.index,self.otype,self.prop1,0xFFFFFFFF))
                ret = False
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


class TDObjectNumberPtr(TDObjectVoid):
    """ Connector with Number Pointer as data

    Stores no additional data, so handling is identical to Void connector.
    """
    pass

class TDObjectString(TDObjectBlob):
    pass


class TDObjectPath(TDObjectBlob):
    pass


class TDObjectPicture(TDObjectBlob):
    pass


class TDObjectSubString(TDObjectBlob):
    pass


class TDObjectPolyVI(TDObjectBlob):
    pass


class TDObjectFunction(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.fflags = 0
        self.pattern = 0
        self.field6 = 0
        self.field7 = 0
        self.hasThrall = 0

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        count = readVariableSizeFieldU2p2(bldata)
        # Create _separate_ empty namespace for each connector
        self.clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = readVariableSizeFieldU2p2(bldata)
            self.clients[i].index = cli_idx
        # end of MultiContainer part
        self.fflags = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.pattern = int.from_bytes(bldata.read(2), byteorder='big', signed=False)

        if isGreaterOrEqVersion(ver, 10,0,0,stage="alpha"):
            for i in range(count):
                cli_flags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
                self.clients[i].flags = cli_flags
        else:
            for i in range(count):
                cli_flags = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
                self.clients[i].flags = cli_flags

        for i in range(count):
            self.clients[i].thrallSources = []
        if isGreaterOrEqVersion(ver, 8,0,0,stage="beta"):
            self.hasThrall = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            if self.hasThrall != 0:
                for i in range(count):
                    thrallSources = []
                    while True:
                        k = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
                        if k == 0:
                            break
                        if isGreaterOrEqVersion(ver, 8,2,0,stage="beta"):
                            k = k - 1
                        thrallSources.append(k)
                    self.clients[i].thrallSources = thrallSources
        else:
            self.hasThrall = 0

        if (self.fflags & 0x0800) != 0:
            self.field6 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            self.field7 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if (self.fflags & 0x8000) != 0:
            # If the flag is set, then the last client is special - comes from here, not the standard list
            client = SimpleNamespace()
            client.index = readVariableSizeFieldU2p2(bldata)
            client.flags = 0
            client.thrallSources = []
            self.clients.append(client)

        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x11000000)
        data_buf = b''

        clients = self.clients.copy()
        spec_cli = None
        if (self.fflags & 0x8000) != 0:
            # Store last client separately, remove it from normal list
            spec_cli = clients.pop()

        data_buf += prepareVariableSizeFieldU2p2(len(clients))
        for client in clients:
            data_buf += prepareVariableSizeFieldU2p2(client.index)
        # end of MultiContainer part
        data_buf += int(self.fflags).to_bytes(2, byteorder='big')
        data_buf += int(self.pattern).to_bytes(2, byteorder='big')

        if isGreaterOrEqVersion(ver, 10,0,0,stage="alpha"):
            for client in clients:
                data_buf += int(client.flags).to_bytes(4, byteorder='big')
        else:
            for client in clients:
                data_buf += int(client.flags).to_bytes(2, byteorder='big')

        if isGreaterOrEqVersion(ver, 8,0,0,stage="beta"):
            data_buf += int(self.hasThrall).to_bytes(2, byteorder='big')
            if self.hasThrall != 0:
                for client in clients:
                    for k in client.thrallSources:
                        if isGreaterOrEqVersion(ver, 8,2,0,stage="beta"):
                            k = k + 1
                        data_buf += int(k).to_bytes(1, byteorder='big')
                    data_buf += int(0).to_bytes(1, byteorder='big')

        if (self.fflags & 0x0800) != 0:
            data_buf += int(self.field6).to_bytes(4, byteorder='big')
            data_buf += int(self.field7).to_bytes(4, byteorder='big')
        if spec_cli is not None:
            data_buf += prepareVariableSizeFieldU2p2(spec_cli.index)

        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        clients = self.clients.copy()
        exp_whole_len = 4
        spec_cli = None
        if (self.fflags & 0x8000) != 0:
            spec_cli = clients.pop()
        exp_whole_len += 2 if len(clients) <= 0x7FFF else 4
        for client in clients:
            exp_whole_len += 2 if client.index <= 0x7FFF else 4
        exp_whole_len += 2 + 2

        if isGreaterOrEqVersion(ver, 10,0,0,stage="alpha"):
            exp_whole_len += 4 * len(clients)
        else:
            exp_whole_len += 2 * len(clients)

        if isGreaterOrEqVersion(ver, 8,0,0,stage="beta"):
            exp_whole_len += 2
            if self.hasThrall != 0:
                for client in clients:
                    exp_whole_len += 1 * len(client.thrallSources)
                    exp_whole_len += 1

        if (self.fflags & 0x0800) != 0:
            exp_whole_len += 8
        if spec_cli is not None:
            exp_whole_len += 2 if spec_cli.index <= 0x7FFF else 4

        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.fflags = int(conn_elem.get("FuncFlags"), 0)
            self.pattern = int(conn_elem.get("Pattern"), 0)
            self.hasThrall = int(conn_elem.get("HasThrall"), 0)
            tmp_val = conn_elem.get("Field6")
            if tmp_val is not None:
                self.field6 = int(tmp_val, 0)
            else:
                self.field6 = 0
            tmp_val = conn_elem.get("Field7")
            if tmp_val is not None:
                self.field7 = int(tmp_val, 0)
            else:
                self.field7 = 0

            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "Client"):
                    client = SimpleNamespace()
                    i = int(subelem.get("Index"), 0)
                    client.index = int(subelem.get("ConnectorIndex"), 0)
                    client.flags = int(subelem.get("Flags"), 0)
                    client.thrallSources = []
                    for sub_subelem in subelem:
                        if (sub_subelem.tag == "ThrallSources"):
                            client.thrallSources += [int(itm,0) for itm in sub_subelem.text.split()]
                        else:
                            raise AttributeError("Connector Client contains unexpected tag")
                    # Grow the list if needed (the clients may be in wrong order)
                    if i >= len(self.clients):
                        self.clients.extend([None] * (i - len(self.clients) + 1))
                    self.clients[i] = client
                else:
                    raise AttributeError("Connector contains unexpected tag")

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        conn_elem.set("FuncFlags", "0x{:X}".format(self.fflags))
        conn_elem.set("Pattern", "0x{:X}".format(self.pattern))
        conn_elem.set("HasThrall", "{:d}".format(self.hasThrall))

        if self.field6 != 0:
            conn_elem.set("Field6", "0x{:X}".format(self.field6))
        if self.field7 != 0:
            conn_elem.set("Field7", "0x{:X}".format(self.field7))

        for i, client in enumerate(self.clients):
            subelem = ET.SubElement(conn_elem,"Client")

            subelem.set("Index", "{:d}".format(i))
            subelem.set("ConnectorIndex", str(client.index))
            subelem.set("Flags", "0x{:04X}".format(client.flags))

            if len(client.thrallSources) > 0:
                strlist = ""
                for k, val in enumerate(client.thrallSources):
                    strlist += " {:3d}".format(val)

                sub_subelem = ET.SubElement(subelem,"ThrallSources")
                sub_subelem.text = strlist

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if (len(self.clients) > 125):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} clients count {:d}, expected below {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),125+1))
            ret = False
        typeList = None
        if self.topTypeList is not None:
            typeList = self.topTypeList
        else:
            VCTP = self.vi.get('VCTP')
            if VCTP is not None:
                typeList = VCTP.getContent()
        if typeList is not None:
            for i, client in enumerate(self.clients):
                if client.index == -1: # Special case this is how we mark nested client
                    if client.nested is None:
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TD {:d} nested client {:d} does not exist"\
                              .format(self.vi.src_fname,self.index,i))
                        ret = False
                else:
                    if client.index >= len(typeList):
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TD {:d} client {:d} references outranged TD {:d}"\
                              .format(self.vi.src_fname,self.index,i,client.index))
                        ret = False
                pass
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


class TDObjectTypeDef(TDObject):
    """ Connector which stores type definition

    Connectors of this type have a special support in LabView code, where type data
    is replaced by the data from nested connector. But we shouldn't need it here.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.flag1 = 0
        self.labels = []

    def parseRSRCNestedTD(self, bldata, pos):
        """ Parse RSRC data of a connector which is not in main list of connectors

        This is a variant of VCTP.parseRSRCConnector() which assigns index -1 and
        does not store the connector in any list.
        """
        bldata.seek(pos)
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        obj_type, obj_flags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        obj = newTDObject(self.vi, -1, obj_flags, obj_type, self.po)
        bldata.seek(pos)
        # The object length of this nested connector is 4 bytes larger than real thing.
        # Not everyone is aiming for consistency.
        obj.initWithRSRC(bldata, obj_len-4, typeList=self.topTypeList)
        return obj, obj_len

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.flag1 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        if isGreaterOrEqVersion(ver, 8,0,0,4):
            self.labels = readQualifiedName(bldata, self.po)
        else:
            self.labels = [ None ]
            self.labels[0] = readPStr(bldata, 2, self.po)


        # The underlying object is stored here directly, not as index in VCTP list
        pos = bldata.tell()
        self.clients = [ SimpleNamespace() ]
        # In "Vi Explorer" code, the length value of this object is treated differently
        # (decreased by 4); not sure if this is correct and an issue here
        cli, cli_len = self.parseRSRCNestedTD(bldata, pos)
        cli_flags = 0
        self.clients[0].index = cli.index # Nested clients have index -1
        self.clients[0].flags = cli_flags
        self.clients[0].nested = cli
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = b''
        data_buf += int(self.flag1).to_bytes(4, byteorder='big')
        if isGreaterOrEqVersion(ver, 8,0,0,4):
            data_buf += prepareQualifiedName(self.labels, self.po)
        else:
            data_buf += preparePStr(b'/'.join(self.labels), 2, self.po)
        if len(self.clients) != 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} has unexpacted amount of clients; should have 1"\
                  .format(self.vi.src_fname,self.index,self.otype))
        for client in self.clients:
            cli_data_buf = client.nested.prepareRSRCData(avoid_recompute=avoid_recompute)
            cli_data_buf += client.nested.prepareRSRCDataFinish()

            # size of nested connector is computed differently than in main connector
            cli_data_head = int(len(cli_data_buf)+8).to_bytes(2, byteorder='big')
            cli_data_head += int(client.nested.oflags).to_bytes(1, byteorder='big')
            cli_data_head += int(client.nested.otype).to_bytes(1, byteorder='big')

            data_buf += cli_data_head + cli_data_buf

        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 4
        exp_whole_len += 4 + sum((1+len(s)) for s in self.labels)
        for client in self.clients:
            # nested expected size already includes header size
            exp_whole_len += client.nested.expectedRSRCSize()
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXMLNestedTD(self, conn_subelem):
        client = SimpleNamespace()
        i = int(conn_subelem.get("Index"), 0)
        client.index = -1
        client.flags = 0
        obj_type = valFromEnumOrIntString(TD_FULL_TYPE, conn_subelem.get("Type"))
        obj_flags = importXMLBitfields(CONNECTOR_FLAGS, conn_subelem)
        obj = newTDObject(self.vi, client.index, obj_flags, obj_type, self.po)
        client.nested = obj
        obj.initWithXML(conn_subelem)
        return client, i

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.flag1 = int(conn_elem.get("Flag1"), 0)

            self.labels = []
            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "Client"):
                    client, i = self.initWithXMLNestedTD(subelem)
                    if i != 0:
                        raise AttributeError("Connector expected to contain exactly one nested sub-connector")
                    self.clients.append(client)
                elif (subelem.tag == "Label"):
                    i = int(subelem.get("Index"), 0)
                    label = subelem.get("Text").encode(self.vi.textEncoding)
                    # Grow the list if needed (the labels may be in wrong order)
                    if i >= len(self.labels):
                        self.labels.extend([None] * (i - len(self.labels) + 1))
                    self.labels[i] = label
                else:
                    raise AttributeError("Connector contains unexpected tag")

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for client in self.clients:
            if client.index < 0:
                client.nested.initWithXMLLate()
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        conn_elem.set("Flag1", "0x{:X}".format(self.flag1))

        for i, client in enumerate(self.clients):
            subelem = ET.SubElement(conn_elem,"Client")

            subelem.set("Index", "{:d}".format(i))
            subelem.set("Type", "{:s}".format(stringFromValEnumOrInt(TD_FULL_TYPE, client.nested.otype)))
            subelem.set("Nested", "True")
            if self.index >= 0:
                part_fname = "{:s}_{:04d}_cli{:02d}".format(fname_base,self.index,i)
            else:
                part_fname = "{:s}_cli{:02d}".format(fname_base,i)
            client.nested.exportXML(subelem, part_fname)
            client.nested.exportXMLFinish(subelem)

        for i, label in enumerate(self.labels):
            subelem = ET.SubElement(conn_elem,"Label")

            subelem.set("Index", "{:d}".format(i))
            label_text = label.decode(self.vi.textEncoding)
            subelem.set("Text", "{:s}".format(label_text))

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if (len(self.clients) != 1):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} clients count {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),1))
            ret = False
        for i, client in enumerate(self.clients):
            if client.index != -1:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TD {:d} expected to have nested client"\
                      .format(self.vi.src_fname,i))
                ret = False
            pass
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


class TDObjectArray(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.dimensions = [ ]
        self.clients = [ ]

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        ndimensions = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.dimensions = [SimpleNamespace() for _ in range(ndimensions)]
        for dim in self.dimensions:
            flags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            dim.flags = flags >> 24
            dim.fixedSize = flags & 0x00FFFFFF

        self.clients = [ SimpleNamespace() ]
        for client in self.clients:
            cli_idx = readVariableSizeFieldU2p2(bldata)
            cli_flags = 0
            client.index = cli_idx
            client.flags = cli_flags

        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.dimensions)).to_bytes(2, byteorder='big')
        for dim in self.dimensions:
            flags = (dim.flags << 24) | dim.fixedSize
            data_buf += int(flags).to_bytes(4, byteorder='big')
        if len(self.clients) != 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} has unexpacted amount of clients; should have 1"\
                  .format(self.vi.src_fname,self.index,self.otype))
        for client in self.clients:
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2 + 4 * len(self.dimensions)
        for client in self.clients:
            exp_whole_len += ( 2 if (client.index <= 0x7fff) else 4 )
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)

            self.dimensions = []
            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "Dimension"):
                    i = int(subelem.get("Index"), 0)
                    dim = SimpleNamespace()
                    dim.flags = int(subelem.get("Flags"), 0)
                    dim.fixedSize = int(subelem.get("FixedSize"), 0)
                    # Grow the list if needed (the labels may be in wrong order)
                    if i >= len(self.dimensions):
                        self.dimensions.extend([None] * (i - len(self.dimensions) + 1))
                    self.dimensions[i] = dim
                elif (subelem.tag == "Client"):
                    i = int(subelem.get("Index"), 0)
                    client = SimpleNamespace()
                    client.index = int(subelem.get("ConnectorIndex"), 0)
                    client.flags = int(subelem.get("Flags"), 0)
                    # Grow the list if needed (the labels may be in wrong order)
                    if i >= len(self.clients):
                        self.clients.extend([None] * (i - len(self.clients) + 1))
                    self.clients[i] = client
                else:
                    raise AttributeError("Connector contains unexpected tag")

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        for i, dim in enumerate(self.dimensions):
            subelem = ET.SubElement(conn_elem,"Dimension")

            subelem.set("Index", "{:d}".format(i))
            subelem.set("Flags", "0x{:04X}".format(dim.flags))
            subelem.set("FixedSize", "0x{:04X}".format(dim.fixedSize))

        for i, client in enumerate(self.clients):
            subelem = ET.SubElement(conn_elem,"Client")

            subelem.set("Index", "{:d}".format(i))
            subelem.set("ConnectorIndex", str(client.index))
            subelem.set("Flags", "0x{:04X}".format(client.flags))

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if len(self.dimensions) > 64:
            ret = False
        if len(self.clients) != 1:
            ret = False
        if (self.dimensions[0].flags & 0x80) == 0:
            ret = False
        for client in self.clients:
            if self.index == -1: # Are we a nested connector
                pass
            elif client.index >= self.index:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TD {:d} type 0x{:02x} client {:d} is reference to higher index"\
                      .format(self.vi.src_fname,self.index,self.otype,client.index))
                ret = False
            pass
        return ret


class TDObjectBlock(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.blkSize = None

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.blkSize = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        # No more known data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.blkSize).to_bytes(4, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += self.expectedRSRCDataSize()
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def expectedRSRCDataSize(self):
        exp_whole_len = 0
        exp_whole_len += 4
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.initWithXMLInlineData(conn_elem)

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def initWithXMLInlineData(self, conn_elem):
        self.blkSize = int(conn_elem.get("BlockSize"), 0)

    def exportXML(self, conn_elem, fname_base):
        self.parseData()
        conn_elem.set("BlockSize", "0x{:X}".format(self.blkSize))
        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


class TDObjectAlignedBlock(TDObjectBlock):
    def __init__(self, *args):
        super().__init__(*args)
        self.clients = []

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.clients = []
        self.blkSize = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if True:
            client = SimpleNamespace()
            client.index = readVariableSizeFieldU2p2(bldata)
            client.flags = 0
            self.clients.append(client)

        # No more known data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.blkSize).to_bytes(4, byteorder='big')
        for client in self.clients:
            data_buf += prepareVariableSizeFieldU2p2(client.index)
            break # only one client is supported
        return data_buf

    def expectedRSRCDataSize(self):
        exp_whole_len = 0
        exp_whole_len += 4
        for client in self.clients:
            exp_whole_len += ( 2 if (client.index <= 0x7fff) else 4 )
            break # only one client is valid
        return exp_whole_len

    def initWithXMLInlineData(self, conn_elem):
        self.clients = []
        self.blkSize = int(conn_elem.get("BlockSize"), 0)

        for subelem in conn_elem:
            if (subelem.tag == "Client"):
                client = SimpleNamespace()
                client.index = int(subelem.get("ConnectorIndex"), 0)
                client.flags = int(subelem.get("Flags"), 0)
                self.clients.append(client)
            else:
                raise AttributeError("Connector contains unexpected tag")
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()
        conn_elem.set("BlockSize", "0x{:X}".format(self.blkSize))
        for client in self.clients:
            subelem = ET.SubElement(conn_elem,"Client")

            subelem.set("ConnectorIndex", str(client.index))
            subelem.set("Flags", "0x{:04X}".format(client.flags))
        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        typeList = None
        if self.topTypeList is not None:
            typeList = self.topTypeList
        else:
            VCTP = self.vi.get('VCTP')
            if VCTP is not None:
                typeList = VCTP.getContent()
        if typeList is not None:
            for i, client in enumerate(self.clients):
                if client.index == -1: # This is how we mark nested client
                    if client.nested is None:
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TD {:d} nested client {:d} does not exist"\
                              .format(self.vi.src_fname,self.index,i))
                        ret = False
                else:
                    if client.index >= len(typeList):
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TD {:d} client {:d} references outranged TD {:d}"\
                              .format(self.vi.src_fname,self.index,i,client.index))
                        ret = False
                pass
        return ret


class TDObjectRepeatedBlock(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.clients = []
        self.numRepeats = 0

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.clients = []
        self.numRepeats = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if True:
            client = SimpleNamespace()
            client.index = readVariableSizeFieldU2p2(bldata)
            client.flags = 0
            self.clients.append(client)
        # No more known data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.numRepeats).to_bytes(4, byteorder='big')
        for client in self.clients:
            data_buf += prepareVariableSizeFieldU2p2(client.index)
            break # only one client is supported
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 4
        for client in self.clients:
            exp_whole_len += ( 2 if (client.index <= 0x7fff) else 4 )
            break # only one client is valid
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXMLInlineData(self, conn_elem):
        self.clients = []
        self.numRepeats = int(conn_elem.get("NumRepeats"), 0)

        for subelem in conn_elem:
            if (subelem.tag == "Client"):
                client = SimpleNamespace()
                client.index = int(subelem.get("ConnectorIndex"), 0)
                client.flags = int(subelem.get("Flags"), 0)
                self.clients.append(client)
            else:
                raise AttributeError("Connector contains unexpected tag")
        pass

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.initWithXMLInlineData(conn_elem)

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()
        conn_elem.set("NumRepeats", "{:d}".format(self.numRepeats))
        for client in self.clients:
            subelem = ET.SubElement(conn_elem,"Client")

            subelem.set("ConnectorIndex", str(client.index))
            subelem.set("Flags", "0x{:04X}".format(client.flags))
        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        typeList = None
        if self.topTypeList is not None:
            typeList = self.topTypeList
        else:
            VCTP = self.vi.get('VCTP')
            if VCTP is not None:
                typeList = VCTP.getContent()
        if typeList is not None:
            for i, client in enumerate(self.clients):
                if client.index == -1: # This is how we mark nested client
                    if client.nested is None:
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TD {:d} nested client {:d} does not exist"\
                              .format(self.vi.src_fname,self.index,i))
                        ret = False
                else:
                    if client.index >= len(typeList):
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TD {:d} client {:d} references outranged TD {:d}"\
                              .format(self.vi.src_fname,self.index,i,client.index))
                        ret = False
                pass
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


class TDObjectRef(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.reftype = int(REFNUM_TYPE.Generic)
        self.ref_obj = None
        self.items = []
        self.objects = []

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.reftype = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.ref_obj = LVdatatyperef.newTDObjectRef(self.vi, self, self.reftype, self.po)
        if self.ref_obj is not None:
            if (self.po.verbose > 2):
                print("{:s}: TD {:d} type 0x{:02x}, has ref_type=0x{:02X} class {:s}"\
                  .format(self.vi.src_fname,self.index,self.otype,self.reftype,type(self.ref_obj).__name__))
            self.ref_obj.parseRSRCData(bldata)
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.reftype).to_bytes(2, byteorder='big')
        if self.ref_obj is not None:
            data_buf += self.ref_obj.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2
        if self.ref_obj is not None:
            exp_whole_len += self.ref_obj.expectedRSRCSize()
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.reftype = valFromEnumOrIntString(REFNUM_TYPE, conn_elem.get("RefType"))

            self.ref_obj = LVdatatyperef.newTDObjectRef(self.vi, self, self.reftype, self.po)
            if self.ref_obj is not None:
                if (self.po.verbose > 2):
                    print("{:s}: TD {:d} type 0x{:02x}, has ref_type=0x{:02X} class {:s}"\
                      .format(self.vi.src_fname,self.index,self.otype,self.reftype,type(self.ref_obj).__name__))
                self.ref_obj.initWithXML(conn_elem)

            self.clients = []
            self.items = []
            for subelem in conn_elem:
                if (subelem.tag == "Client"):
                    client = SimpleNamespace()
                    i = int(subelem.get("Index"), 0)
                    client.index = int(subelem.get("ConnectorIndex"), 0)
                    client.flags = int(subelem.get("Flags"), 0)
                    if self.ref_obj is not None:
                        self.ref_obj.initWithXMLClient(client, subelem)
                    # Grow the list if needed (the clients may be in wrong order)
                    if i >= len(self.clients):
                        self.clients.extend([None] * (i - len(self.clients) + 1))
                    self.clients[i] = client
                elif (subelem.tag == "Item"):
                    item = SimpleNamespace()
                    i = int(subelem.get("Index"), 0)
                    if self.ref_obj is not None:
                        self.ref_obj.initWithXMLItem(item, subelem)
                    # Grow the list if needed (the items may be in wrong order)
                    if i >= len(self.items):
                        self.items.extend([None] * (i - len(self.items) + 1))
                    self.items[i] = item
                elif (subelem.tag == "LVVariant"):
                    i = int(subelem.get("Index"), 0)
                    obj = LVclasses.LVVariant(i, self.vi, self.po)
                    # Grow the list if needed (the objects may be in wrong order)
                    if i >= len(self.objects):
                        self.objects.extend([None] * (i - len(self.objects) + 1))
                    obj.initWithXML(subelem)
                    self.objects[i] = obj
                else:
                    raise AttributeError("Connector contains unexpected tag")

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        #if self.ref_obj is not None: # currently refnums have no initWithXMLLate
        #    self.ref_obj.initWithXMLLate()
        for obj in self.objects:
            obj.initWithXMLLate()
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        conn_elem.set("RefType", stringFromValEnumOrInt(REFNUM_TYPE, self.reftype))
        if self.ref_obj is not None:
            self.ref_obj.exportXML(conn_elem, fname_base)

        for i, client in enumerate(self.clients):
            subelem = ET.SubElement(conn_elem,"Client")

            subelem.set("Index", "{:d}".format(i))
            subelem.set("ConnectorIndex", str(client.index))
            subelem.set("Flags", "0x{:04X}".format(client.flags))

            if self.ref_obj is not None:
                self.ref_obj.exportXMLClient(client, subelem, fname_base)

        for i, item in enumerate(self.items):
            subelem = ET.SubElement(conn_elem,"Item")

            subelem.set("Index", "{:d}".format(i))

            if self.index >= 0:
                part_fname = "{:s}_{:04d}_itm{:02d}".format(fname_base,self.index,i)
            else:
                part_fname = "{:s}_itm{:02d}".format(fname_base,i)

            if self.ref_obj is not None:
                self.ref_obj.exportXMLItem(item, subelem, part_fname)

        for i, obj in enumerate(self.objects):
            subelem = ET.SubElement(conn_elem,"LVObject") # Export function from the object may overwrite the tag

            subelem.set("Index", "{:d}".format(i))

            if self.index >= 0:
                part_fname = "{:s}_{:04d}_lvo{:02d}".format(fname_base,self.index,i)
            else:
                part_fname = "{:s}_lvo{:02d}".format(fname_base,i)

            obj.exportXML(subelem, part_fname)

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if self.ref_obj is not None:
            if not self.ref_obj.checkSanity():
                ret = False
        for client in self.clients:
            if self.index == -1: # Are we a nested connector
                pass
            elif client.index >= self.index:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TD {:d} type 0x{:02x} reftype {:d} client {:d} is reference to higher index"\
                      .format(self.vi.src_fname,self.index,self.otype,self.reftype,client.index))
                ret = False
        return ret

    def refType(self):
        if self.reftype not in set(item.value for item in REFNUM_TYPE):
            return self.reftype
        return REFNUM_TYPE(self.reftype)


class TDObjectCluster(TDObject):
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        count = readVariableSizeFieldU2p2(bldata)
        # Create _separate_ empty namespace for each connector
        self.clients = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            cli_idx = readVariableSizeFieldU2p2(bldata)
            cli_flags = 0
            self.clients[i].index = cli_idx
            self.clients[i].flags = cli_flags
        # No more data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.clients)).to_bytes(2, byteorder='big')
        for client in self.clients:
            data_buf += int(client.index).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2 + 2 * len(self.clients)
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)

            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "Client"):
                    client = SimpleNamespace()
                    i = int(subelem.get("Index"), 0)
                    client.index = int(subelem.get("ConnectorIndex"), 0)
                    client.flags = 0
                    # Grow the list if needed (the clients may be in wrong order)
                    if i >= len(self.clients):
                        self.clients.extend([None] * (i - len(self.clients) + 1))
                    self.clients[i] = client
                else:
                    raise AttributeError("Connector contains unexpected tag")

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for client in self.clients:
            if client.index < 0:
                client.nested.initWithXMLLate()
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        for i, client in enumerate(self.clients):
            subelem = ET.SubElement(conn_elem,"Client")

            subelem.set("Index", str(i))
            subelem.set("ConnectorIndex", str(client.index))

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if len(self.clients) > 500:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} has {:d} clients, expected below {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),500+1))
            ret = False
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


class TDObjectMeasureData(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.flavor = None

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.flavor = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        # No more known data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.flavor).to_bytes(2, byteorder='big')
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.flavor = valFromEnumOrIntString(MEASURE_DATA_FLAVOR, conn_elem.get("Flavor"))

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()
        conn_elem.set("Flavor", "{:s}".format(stringFromValEnumOrInt(MEASURE_DATA_FLAVOR, self.flavor)))
        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if self.flavor > 127: # Not sure how many cluster formats are there
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} flavor {:d}, expected below {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,self.flavor,127+1))
            ret = False
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret

    def dtFlavor(self):
        if self.flavor not in set(item.value for item in MEASURE_DATA_FLAVOR):
            return self.flavor
        return MEASURE_DATA_FLAVOR(self.flavor)


class TDObjectFixedPoint(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.ranges = []

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        field1C = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        field1E = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        field20 = int.from_bytes(bldata.read(4), byteorder='big', signed=False)

        self.dataVersion = (field1C) & 0x0F
        self.rangeFormat = (field1C >> 4) & 0x03
        self.dataEncoding = (field1C >> 6) & 0x01
        self.dataEndianness = (field1C >> 7) & 0x01
        self.dataUnit = (field1C >> 8) & 0x07
        self.allocOv = (field1C >> 11) & 0x01
        self.leftovFlags = (field1C >> 8) & 0xF6
        self.field1E = field1E
        self.field20 = field20

        count = 3
        ranges = [SimpleNamespace() for _ in range(count)]
        for i, rang in enumerate(ranges):
            rang.prop1 = None
            rang.prop2 = None
            rang.prop3 = None
            if self.rangeFormat == 0:
                valtup = struct.unpack('>d', bldata.read(8))
            elif self.rangeFormat == 1:
                if (self.field1E > 0x40) or (self.dataVersion > 0):
                    rang.prop1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
                    rang.prop2 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
                    rang.prop3 = int.from_bytes(bldata.read(4), byteorder='big', signed=True)
                    valtup = struct.unpack('>d', bldata.read(8))
                else:
                    valtup = struct.unpack('>d', bldata.read(8))
            rang.value = valtup[0]
            pass
        self.ranges = ranges
        # No more data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''

        field1C = \
          ((self.dataVersion & 0x0F)) | \
          ((self.rangeFormat & 0x03) << 4) | \
          ((self.dataEncoding & 0x01) << 6) | \
          ((self.dataEndianness & 0x01) << 7) | \
          ((self.dataUnit & 0x07) << 8) | \
          ((self.allocOv & 0x01) << 11) | \
          ((self.leftovFlags & 0xF6) << 8)
        data_buf += int(field1C).to_bytes(2, byteorder='big')
        data_buf += int(self.field1E).to_bytes(2, byteorder='big')
        data_buf += int(self.field20).to_bytes(4, byteorder='big')

        for i, rang in enumerate(self.ranges):
            if self.rangeFormat == 0:
                data_buf += struct.pack('>d', rang.value)
            elif self.rangeFormat == 1:
                if (self.field1E > 0x40) or (self.dataVersion > 0):
                    data_buf += int(rang.prop1).to_bytes(2, byteorder='big')
                    data_buf += int(rang.prop2).to_bytes(2, byteorder='big')
                    data_buf += int(rang.prop3).to_bytes(4, byteorder='big')
                    data_buf += struct.pack('>d', rang.value)
                else:
                    data_buf += struct.pack('>d', rang.value)
            pass
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2 + 2 + 4
        if self.rangeFormat == 0:
            exp_whole_len += 8 * len(self.ranges)
        elif self.rangeFormat == 1:
            if (self.field1E > 0x40) or (self.dataVersion > 0):
                exp_whole_len += (2+2+4+8) * len(self.ranges)
            else:
                exp_whole_len += 8 * len(self.ranges)
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)


            self.dataVersion = int(conn_elem.get("DataVersion"), 0)
            self.rangeFormat = int(conn_elem.get("RangeFormat"), 0)
            self.dataEncoding = int(conn_elem.get("DataEncoding"), 0)
            self.dataEndianness = int(conn_elem.get("DataEndianness"), 0)
            self.dataUnit = int(conn_elem.get("DataUnit"), 0)
            self.allocOv = int(conn_elem.get("AllocOv"), 0)
            self.leftovFlags = int(conn_elem.get("LeftovFlags"), 0)
            self.field1E = int(conn_elem.get("Field1E"), 0)
            self.field20 = int(conn_elem.get("Field20"), 0)

            self.ranges = []
            for subelem in conn_elem:
                if (subelem.tag == "Range"):
                    i = int(subelem.get("Index"), 0)
                    rang = SimpleNamespace()
                    rang.prop1 = None
                    rang.prop2 = None
                    rang.prop3 = None

                    prop1 = subelem.get("Prop1")
                    if prop1 is not None:
                        rang.prop1 = int(prop1, 0)
                    prop2 = subelem.get("Prop2")
                    if prop2 is not None:
                        rang.prop2 = int(prop2, 0)
                    prop3 = subelem.get("Prop3")
                    if prop3 is not None:
                        rang.prop3 = int(prop3, 0)
                    valstr = subelem.get("Value")
                    if valstr is not None:
                        rang.value = float(valstr)

                    # Grow the list if needed (the rangs may be in wrong order)
                    if i >= len(self.ranges):
                        self.ranges.extend([None] * (i - len(self.ranges) + 1))
                    self.ranges[i] = rang
                else:
                    raise AttributeError("Connector contains unexpected tag")

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        conn_elem.set("DataVersion", "{:d}".format(self.dataVersion))
        conn_elem.set("RangeFormat", "{:d}".format(self.rangeFormat))
        conn_elem.set("DataEncoding", "{:d}".format(self.dataEncoding))
        conn_elem.set("DataEndianness", "{:d}".format(self.dataEndianness))
        conn_elem.set("DataUnit", "{:d}".format(self.dataUnit))
        conn_elem.set("AllocOv", "{:d}".format(self.allocOv))
        conn_elem.set("LeftovFlags", "{:d}".format(self.leftovFlags))
        conn_elem.set("Field1E", "{:d}".format(self.field1E))
        conn_elem.set("Field20", "{:d}".format(self.field20))

        for i, rang in enumerate(self.ranges):
            subelem = ET.SubElement(conn_elem,"Range")

            subelem.set("Index", "{:d}".format(i))
            if self.rangeFormat == 0:
                # 64-bit float has 17 digit precision
                subelem.set("Value", "{:.17g}".format(rang.value))
            elif self.rangeFormat == 1:
                if (self.field1E > 0x40) or (self.dataVersion > 0):
                    subelem.set("Prop1", "{:d}".format(rang.prop1))
                    subelem.set("Prop2", "{:d}".format(rang.prop2))
                    subelem.set("Prop3", "{:d}".format(rang.prop3))
                    subelem.set("Value", "{:.17g}".format(rang.value))
                else:
                    subelem.set("Value", "{:.17g}".format(rang.value))
            pass

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if len(self.clients) > 500:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} has {:d} clients, expected below {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),500+1))
            ret = False
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret

class TDObjectSingleContainer(TDObject):
    def __init__(self, *args):
        super().__init__(*args)
        self.prop1 = 0
        self.clients = []

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.clients = []
        if True:
            client = SimpleNamespace()
            client.index = readVariableSizeFieldU2p2(bldata)
            client.flags = 0
            self.clients.append(client)

        # No more data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for client in self.clients:
            data_buf += prepareVariableSizeFieldU2p2(client.index)
            break # only one client is supported

        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        for client in self.clients:
            exp_whole_len += ( 2 if (client.index <= 0x7fff) else 4 )
            break # only one client is valid
        if self.label is not None:
            label_len = 1 + len(self.label)
            if label_len % 2 > 0: # Include padding
                label_len += 2 - (label_len % 2)
            exp_whole_len += label_len
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TD {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "Client"):
                    client = SimpleNamespace()
                    i = int(subelem.get("Index"), 0)
                    client.index = int(subelem.get("ConnectorIndex"), 0)
                    client.flags = int(subelem.get("Flags"), 0)
                    # Grow the list if needed (the clients may be in wrong order)
                    if i >= len(self.clients):
                        self.clients.extend([None] * (i - len(self.clients) + 1))
                    self.clients[i] = client
                else:
                    raise AttributeError("Connector contains unexpected tag")

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for client in self.clients:
            if client.index < 0:
                client.nested.initWithXMLLate()
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        for i, client in enumerate(self.clients):
            subelem = ET.SubElement(conn_elem,"Client")

            subelem.set("Index", "{:d}".format(i))
            subelem.set("ConnectorIndex", str(client.index))
            subelem.set("Flags", "0x{:04X}".format(client.flags))

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = True
        if (len(self.clients) != 1):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} clients count {:d}, expected exactly {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),1))
            ret = False
        typeList = None
        if self.topTypeList is not None:
            typeList = self.topTypeList
        else:
            VCTP = self.vi.get('VCTP')
            if VCTP is not None:
                typeList = VCTP.getContent()
        if typeList is not None:
            for i, client in enumerate(self.clients):
                if client.index == -1: # This is how we mark nested client
                    if client.nested is None:
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TD {:d} nested client {:d} does not exist"\
                              .format(self.vi.src_fname,self.index,i))
                        ret = False
                else:
                    if client.index >= len(typeList):
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TD {:d} client {:d} references outranged TD {:d}"\
                              .format(self.vi.src_fname,self.index,i,client.index))
                        ret = False
                pass
        exp_whole_len = self.expectedRSRCSize()
        if len(self.raw_data) != exp_whole_len:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TD {:d} type 0x{:02x} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.raw_data),exp_whole_len))
            ret = False
        return ret


def tdEnToName(tdEn):
    """ Return text name for TD_FULL_TYPE element

    Try to keep naming convention which LV uses.
    """
    if LV_INTERNAL_TD_NAMES.has_value(int(tdEn)):
        lvtdEn = LV_INTERNAL_TD_NAMES(tdEn)
        tdName = lvtdEn.name
    elif isinstance(tdEn, TD_FULL_TYPE):
        tdName = tdEn.name
        raise NotImplementedError("Value {} not in {}.".format(tdEn.name,LV_INTERNAL_TD_NAMES.__name__))
    else:
        tdName = "TD{:02X}".format(tdEn)
    return tdName

def tdNameToEnum(tdName):
    tagEn = None

    if LV_INTERNAL_TD_NAMES.has_name(tdName):
        lvtdEn = LV_INTERNAL_TD_NAMES[tdName]
        tagEn = TD_FULL_TYPE(lvtdEn.value)

    if tagEn is None:
        if tdName == LVclasses.LVVariant.__name__:
            tagEn = TD_FULL_TYPE.LVVariant
        elif tdName == LVclasses.OleVariant.__name__:
            tagEn = TD_FULL_TYPE.LVVariant

    if tagEn is None:
        flavorEn = mdFlavorNameToEnum(tdName)
        if flavorEn is not None:
            tagEn = TD_FULL_TYPE.MeasureData

    if tagEn is None:
        refnumEn = LVdatatyperef.refnumNameToEnum(tdName)
        if refnumEn is not None:
            tagEn = TD_FULL_TYPE.Refnum

    # no direct conversion from TD_FULL_TYPE names
    # These would be probllematic as it has no has_name().
    # So just generic int value support
    if tagEn is None:
        tagParse = re.match("^TD([0-9A-F]{2,4})$", tdName)
        if tagParse is not None:
            tagEn = int(tagParse[1], 16)

    return tagEn


def mdFlavorEnToName(flavorEn):
    """ Return text name for MEASURE_DATA_FLAVOR element
    """
    if LV_INTERNAL_MEAS_FLAVOR_NAMES.has_value(int(flavorEn)):
        lvflavorEn = LV_INTERNAL_MEAS_FLAVOR_NAMES(flavorEn)
        flavName = lvflavorEn.name
    elif isinstance(flavorEn, MEASURE_DATA_FLAVOR):
        flavName = flavorEn.name
        raise NotImplementedError("Value {} not in {}.".format(flavorEn.name,LV_INTERNAL_MEAS_FLAVOR_NAMES.__name__))
    else:
        flavName = "MeasureData{:02X}".format(flavorEn)
    return flavName

def mdFlavorNameToEnum(flavName):
    """ Return MEASURE_DATA_FLAVOR element for given text name
    """
    flavorEn = None

    if LV_INTERNAL_MEAS_FLAVOR_NAMES.has_name(flavName):
        lvflavEn = LV_INTERNAL_MEAS_FLAVOR_NAMES[flavName]
        flavorEn = MEASURE_DATA_FLAVOR(lvflavEn.value)

    # no direct conversion from MEASURE_DATA_FLAVOR names
    # These would be probllematic as it has no has_name().
    # So just generic int value support
    if flavorEn is None:
        tagParse = re.match("^MeasureData([0-9A-F]{2,4})$", flavName)
        if tagParse is not None:
            flavorEn = int(tagParse[1], 16)

    return flavorEn


def newErrorCluster(vi, idx, obj_flags, po):
    """ Error information is transferred in a specific Cluster
    """
    # Content (fields) of the error cluster
    tdList = []

    tdErrEnt = SimpleNamespace() # error status
    tdErrEnt.index = -1
    tdErrEnt.flags = 0
    tdErrEnt.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.Boolean, po)
    tdList.append(tdErrEnt)

    tdErrEnt = SimpleNamespace() # error code
    tdErrEnt.index = -1
    tdErrEnt.flags = 0
    tdErrEnt.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.NumInt32, po)
    tdList.append(tdErrEnt)

    tdErrEnt = SimpleNamespace() # error source
    tdErrEnt.index = -1
    tdErrEnt.flags = 0
    tdErrEnt.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.String, po)
    tdList.append(tdErrEnt)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster

def newDigitalTableCluster(vi, idx, obj_flags, po):
    """ The DigitalTable is a Cluster with specific things inside
    """
    # make list of fields
    tdList = []

    tdDigTabEnt = SimpleNamespace() # DigitalTable transitions
    tdDigTabEnt.index = -1
    tdDigTabEnt.flags = 0
    tdDigTabEnt.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.Array, po)
    tdDigTabEnt.nested.dimensions = [SimpleNamespace() for _ in range(1)]
    for dim in tdDigTabEnt.nested.dimensions:
        dim.flags = 0
        dim.fixedSize = -1
    tdDigTabEnt.nested.clients = [ SimpleNamespace() ]
    for client in tdDigTabEnt.nested.clients:
        cli_flags = 0
        client.index = -1
        client.flags = 0
        client.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.NumUInt32, po)
    tdList.append(tdDigTabEnt)

    tdDigTabEnt = SimpleNamespace() # DigitalTable data
    tdDigTabEnt.index = -1
    tdDigTabEnt.flags = 0
    tdDigTabEnt.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.Array, po)
    tdDigTabEnt.nested.dimensions = [SimpleNamespace() for _ in range(2)]
    for dim in tdDigTabEnt.nested.dimensions:
        dim.flags = 0
        dim.fixedSize = -1
    tdDigTabEnt.nested.clients = [ SimpleNamespace() ]
    for client in tdDigTabEnt.nested.clients:
        cli_flags = 0
        client.index = -1
        client.flags = 0
        client.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.NumUInt8, po)
    tdList.append(tdDigTabEnt)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster


def newDigitalWaveformCluster(vi, idx, obj_flags, po):
    """ The DigitalWaveform is a Cluster with specific things inside
    """
    tdList = []
    tdEntry = SimpleNamespace() # t0
    tdEntry.index = -1
    tdEntry.flags = 0
    # Use block of 16 bytes as Timestamp
    tdEntry.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.Block, po)
    tdEntry.nested.blkSize = 16
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # dt
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.NumFloat64, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # Y
    tdEntry.index = -1
    tdEntry.flags = 0
    # The DigitalTable is a Cluster with specific things inside
    tdEntry.nested = newDigitalTableCluster(vi, -1, 0, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # error
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newErrorCluster(vi, -1, 0, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # attributes
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.LVVariant, po)
    tdList.append(tdEntry)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster


def newAnalogWaveformCluster(vi, idx, obj_flags, tdInner, po):
    """ The AnalogWaveform is a Cluster with specific things inside
    """
    tdList = []
    tdEntry = SimpleNamespace() # t0
    tdEntry.index = -1
    tdEntry.flags = 0
    # Use block of 16 bytes as Timestamp
    tdEntry.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.Block, po)
    tdEntry.nested.blkSize = 16
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # dt
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.NumFloat64, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # Y
    tdEntry.index = -1
    tdEntry.flags = 0
    # The AnalogTable is a Cluster with specific things inside
    tdEntry.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.Array, po)
    tdEntry.nested.dimensions = [SimpleNamespace() for _ in range(1)]
    for dim in tdEntry.nested.dimensions:
        dim.flags = 0
        dim.fixedSize = -1
    tdEntry.nested.clients = [ SimpleNamespace() ]
    for client in tdEntry.nested.clients:
        cli_flags = 0
        client.index = -1
        client.flags = 0
        client.nested = tdInner
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # error
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newErrorCluster(vi, -1, 0, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # attributes
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.LVVariant, po)
    tdList.append(tdEntry)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster


def newDynamicTableCluster(vi, idx, obj_flags, po):
    """ The DynamicTable is a Cluster with specific things inside
    """
    # make list of fields
    tdList = []

    tdTabEnt = SimpleNamespace()
    tdTabEnt.index = -1
    tdTabEnt.flags = 0
    tdTabEnt.nested = newTDObject(vi, -1, 0, TD_FULL_TYPE.Array, po)
    tdTabEnt.nested.dimensions = [SimpleNamespace() for _ in range(1)]
    for dim in tdTabEnt.nested.dimensions:
        dim.flags = 0
        dim.fixedSize = -1
    tdTabEnt.nested.clients = [ SimpleNamespace() ]
    for client in tdTabEnt.nested.clients:
        client.index = -1
        client.flags = 0
        # data inside as for MEASURE_DATA_FLAVOR.Float64Waveform
        tdInner = newTDObject(vi, -1, 0, TD_FULL_TYPE.NumFloat64, po)
        client.nested = newAnalogWaveformCluster(vi, -1, 0, tdInner, po)
    tdList.append(tdTabEnt)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster

def newOldFloat64WaveformCluster(vi, idx, obj_flags, po):
    """ The OldFloat64 Waveform is a Cluster with specific things inside
    """
    #TODO this is not enough, some changes are required in the cluster
    tdInner = newTDObject(self.vi, -1, 0, TD_FULL_TYPE.NumFloat64, self.po)
    tdCluster = newAnalogWaveformCluster(self.vi, -1, 0, tdInner, self.po)
    return tdCluster


def newTDObject(vi, idx, obj_flags, obj_type, po):
    """ Creates and returns new terminal object with given parameters
    """
    # Try types for which we have specific constructors
    ctor = {
        TD_FULL_TYPE.Void: TDObjectVoid,
        #TD_FULL_TYPE.Num*: TDObjectNumber, # Handled by main type
        #TD_FULL_TYPE.Unit*: TDObjectNumber, # Handled by main type
        #TD_FULL_TYPE.Boolean*: TDObjectBool, # Handled by main type
        TD_FULL_TYPE.String: TDObjectString,
        TD_FULL_TYPE.Path: TDObjectPath,
        TD_FULL_TYPE.Picture: TDObjectPicture,
        TD_FULL_TYPE.CString: TDObjectCString,
        TD_FULL_TYPE.PasString: TDObjectPasString,
        TD_FULL_TYPE.Tag: TDObjectTag,
        TD_FULL_TYPE.SubString: TDObjectSubString,
        #TD_FULL_TYPE.*Array*: TDObjectArray, # Handled by main type
        TD_FULL_TYPE.Cluster: TDObjectCluster,
        TD_FULL_TYPE.LVVariant: TDObjectLVVariant,
        TD_FULL_TYPE.MeasureData: TDObjectMeasureData,
        TD_FULL_TYPE.ComplexFixedPt: TDObjectFixedPoint,
        TD_FULL_TYPE.FixedPoint: TDObjectFixedPoint,
        TD_FULL_TYPE.Block: TDObjectBlock,
        TD_FULL_TYPE.TypeBlock: TDObjectSingleContainer,
        TD_FULL_TYPE.VoidBlock: TDObjectSingleContainer,
        TD_FULL_TYPE.AlignedBlock: TDObjectAlignedBlock,
        TD_FULL_TYPE.RepeatedBlock: TDObjectRepeatedBlock,
        TD_FULL_TYPE.AlignmntMarker: TDObjectSingleContainer,
        TD_FULL_TYPE.Ptr: TDObjectNumberPtr,
        TD_FULL_TYPE.PtrTo: TDObjectSingleContainer,
        TD_FULL_TYPE.Function: TDObjectFunction,
        TD_FULL_TYPE.TypeDef: TDObjectTypeDef,
        TD_FULL_TYPE.PolyVI: TDObjectPolyVI,
    }.get(obj_type, None)
    if ctor is None:
        # If no specific constructor - go by general type
        obj_main_type = obj_type >> 4
        ctor = {
            TD_MAIN_TYPE.Number: TDObjectNumber,
            TD_MAIN_TYPE.Unit: TDObjectNumber,
            TD_MAIN_TYPE.Bool: TDObjectBool,
            TD_MAIN_TYPE.Blob: TDObject,
            TD_MAIN_TYPE.Array: TDObjectArray,
            TD_MAIN_TYPE.Cluster: TDObject,
            TD_MAIN_TYPE.Block: TDObject,
            TD_MAIN_TYPE.Ref: TDObjectRef,
            TD_MAIN_TYPE.NumberPointer: TDObject,
            TD_MAIN_TYPE.Terminal: TDObject,
            TD_MAIN_TYPE.Void: TDObject, # With the way we get main_type, this condition is impossible
        }.get(obj_main_type, TDObject) # Void is the default type in case of no match
    return ctor(vi, idx, obj_flags, obj_type, po)

