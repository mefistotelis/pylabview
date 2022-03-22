# -*- coding: utf-8 -*-

""" LabView RSRC file format Data Type Descriptors.

    Virtual Consolidated Data Types are stored inside VCTP block.
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
import LVxml as ET
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
    """ known types of Type Descriptors

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


class TYPEDESC_FLAGS(enum.Enum):
    """ Type Descriptor flags
    """
    Bit0 = 1 << 0	# unknown
    Bit1 = 1 << 1	# unknown
    Bit2 = 1 << 2	# unknown
    Bit3 = 1 << 3	# unknown
    Bit4 = 1 << 4	# unknown
    Bit5 = 1 << 5	# unknown
    HasLabel = 1 << 6	# After TD data, there is a string label stored
    Bit7 = 1 << 7	# unknown


class TM_FLAGS(enum.IntEnum):
    """ Type Map Flags
    """
    TMFBit0 = 1 << 0	# IsDSAlignPadding?
    TMFBit1 = 1 << 1	# IsStripChartRec?
    TMFBit2 = 1 << 2	# IsFPDCOOpData
    TMFBit3 = 1 << 3	# unknown
    TMFBit4 = 1 << 4	# IsChartHist
    TMFBit5 = 1 << 5	# unknown
    TMFBit6 = 1 << 6	# unknown
    TMFBit7 = 1 << 7	# IsSubType
    TMFBit8 = 1 << 8	# unknown
    TMFBit9 = 1 << 9	# unknown
    TMFBit10 = 1 << 10	# unknown
    TMFBit11 = 1 << 11	# unknown
    TMFBit12 = 1 << 12	# unknown
    TMFBit13 = 1 << 13	# HasSaveData Informs whether the content is stored in DFDS
    TMFBit14 = 1 << 14	# unknown
    TMFBit15 = 1 << 15	# unknown
    TMFBit16 = 1 << 16	# unknown
    TMFBit17 = 1 << 17	# unknown
    TMFBit18 = 1 << 18	# unknown
    TMFBit19 = 1 << 19	# unknown
    TMFBit20 = 1 << 20	# unknown
    TMFBit21 = 1 << 21	# unknown
    TMFBit22 = 1 << 22	# unknown
    TMFBit23 = 1 << 23	# unknown
    TMFBit24 = 1 << 24	# unknown
    TMFBit25 = 1 << 25	# unknown
    TMFBit26 = 1 << 26	# unknown
    TMFBit27 = 1 << 27	# unknown
    TMFBit28 = 1 << 28	# unknown
    TMFBit29 = 1 << 29	# unknown
    TMFBit30 = 1 << 30	# unknown
    TMFBit31 = 1 << 31	# unknown


class TAG_TYPE(enum.Enum):
    """ Type of tag
    """
    Unknown0 =	0
    SharedVarCtl =		1
    DAQChannelOld =		2
    IVILogicalName =	3
    VISArsrcName =		4
    UserDefined =		5
    FldPointIOPoint =	7
    MotionResource =	8
    DAQmxTaskName =		9
    DAQmxChannel =		10
    DAQmxScaleName =	11
    DAQmxDeviceName =	12
    DAQmxTerminal =		13
    DAQmxPhysChannel =	14
    DAQmxUnkn15 =		15
    DAQmxSwitch =		16


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
    """ Base class for any Type Descriptor
    """

    def __init__(self, vi, blockref, idx, obj_flags, obj_type, po):
        """ Creates new Type Descriptor object, capable of handling generic TD data.
        """
        self.vi = vi
        self.blockref = blockref
        self.po = po
        self.index = idx
        self.oflags = obj_flags
        self.otype = obj_type
        # Dependencies to other types are either indexes in Consolidated List, or locally stored topTypeList
        self.topTypeList = None
        self.label = None
        self.purpose = ""
        self.size = None

        if self.__doc__:
            self.full_name = self.__doc__.split('\n')[0].strip()
        else:
            self.full_name = ""

        self.raw_data = None
        # Whether RAW data has been updated and RSRC parsing is required to update properties
        self.raw_data_updated = False
        # Whether any properties have been updated and preparation of new RAW data is required
        self.parsed_data_updated = False

    def setOwningList(self, typeList=None):
        """ Sets a list of TDs which owns this TD.
        """
        self.topTypeList = typeList

    def setPurposeText(self, purpose):
        self.purpose = purpose

    def initWithRSRC(self, bldata, obj_len):
        """ Early part of Type Descriptor loading from RSRC file

        At the point it is executed, other sections are inaccessible.
        """
        self.size = obj_len
        self.raw_data = bldata.read(obj_len)
        self.raw_data_updated = True

    def initWithXMLInlineStart(self, td_elem):
        """ Early part of Type Descriptor loading from XML file using Inline formats

        That is simply a common part used in all overloaded initWithXML(),
        separated only to avoid code duplication.
        """
        self.label = None
        label_text = td_elem.get("Label")
        if label_text is not None:
            self.label = label_text.encode(self.vi.textEncoding)
        self.parsed_data_updated = True

    def initWithXML(self, td_elem):
        """ Early part of Type Descriptor loading from XML file

        At the point it is executed, other sections are inaccessible.
        To be overriden by child classes which want to load more properties from XML.
        """
        fmt = td_elem.get("Format")
        # TODO the inline block belongs to inheriting classes, not here - move
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(td_elem)

            self.updateData(avoid_recompute=True)

        elif fmt == "bin":# Format="bin" - the content is stored separately as raw binary data
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {}, reading BIN file '{}'"\
                  .format(self.vi.src_fname,self.index,td_elem.get("File")))
            # If there is label in binary data, set our label property to non-None value
            self.label = None
            if (self.oflags & TYPEDESC_FLAGS.HasLabel.value) != 0:
                self.label = b""

            bin_path = os.path.dirname(self.vi.src_fname)
            if len(bin_path) > 0:
                bin_fname = bin_path + '/' + td_elem.get("File")
            else:
                bin_fname = td_elem.get("File")
            with open(bin_fname, "rb") as bin_fh:
                data_buf = bin_fh.read()
            data_head = int(len(data_buf)+4).to_bytes(2, byteorder='big', signed=False)
            data_head += int(self.oflags).to_bytes(1, byteorder='big', signed=False)
            data_head += int(self.otype).to_bytes(1, byteorder='big', signed=False)
            self.setData(data_head+data_buf)
            self.parsed_data_updated = False
        else:
            raise NotImplementedError("Unsupported TypeDesc {} Format '{}'.".format(self.index,fmt))
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
        """ Implements final stage of setting Type Descriptor properties from RSRC file

        Can use other TDs and other blocks.
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
        """ Does generic part of RSRC Type Descriptor parsing and marks the parse as finished

        Really, it mostly implements setting TypeDesc label from RSRC file.
        The label behaves in the same way for every TypeDesc type, so this function
        is really a type-independent part of parseRSRCData().
        """
        if (self.oflags & TYPEDESC_FLAGS.HasLabel.value) != 0:
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
                    eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} label text not found"\
                      .format(self.vi.src_fname, self.index, self.otype))
                self.label = b""
            elif i > 0:
                if (self.po.verbose > 0):
                    eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} has label not immediatelly following data"\
                      .format(self.vi.src_fname, self.index, self.otype))
        self.raw_data_updated = False

    def parseXMLData(self):
        """ Implements final stage of setting Type Descriptor properties from XML

        Can use other TDs and other blocks.
        """
        self.parsed_data_updated = False

    def parseData(self):
        """ Parse data of specific section and place it as Type Descriptor properties
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
        pass

    def needParseData(self):
        """ Returns if the Type Descriptor did not had its data parsed yet

            After a call to parseData(), or after filling the data manually, this should
            return True. Otherwise, False.
        """
        return self.raw_data_updated or self.parsed_data_updated

    def prepareRSRCData(self, avoid_recompute=False):
        """ Returns part of the Type Descriptor data re-created from properties.

        To be overloaded in classes for specific TypeDesc types.
        """
        if self.raw_data:
            data_buf = self.raw_data[4:]
        else:
            data_buf = b''

        # Remove label from the end - use the algorithm from parseRSRCDataFinish() for consistency
        if (self.oflags & TYPEDESC_FLAGS.HasLabel.value) != 0:
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
            self.oflags |= TYPEDESC_FLAGS.HasLabel.value
            if len(self.label) > 255:
                self.label = self.label[:255]
            data_buf += preparePStr(self.label, 1, self.po)
        else:
            self.oflags &= ~TYPEDESC_FLAGS.HasLabel.value

        if len(data_buf) % 2 > 0:
            padding_len = 2 - (len(data_buf) % 2)
            data_buf += (b'\0' * padding_len)

        return data_buf

    def expectedRSRCLabelSize(self):
        if self.label is None:
            return 0
        label_len = 1 + len(self.label)
        if label_len % 2 > 0: # Include padding
            label_len += 2 - (label_len % 2)
        return label_len

    def expectedRSRCSize(self):
        """ Returns expected RAW data size of this Type Descriptor.

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

        data_head = int(len(data_buf)+4).to_bytes(2, byteorder='big', signed=False)
        data_head += int(self.oflags).to_bytes(1, byteorder='big', signed=False)
        data_head += int(self.otype).to_bytes(1, byteorder='big', signed=False)

        self.setData(data_head+data_buf, incomplete=avoid_recompute)

    def exportXML(self, td_elem, fname_base):
        self.parseData()

        # TODO the inline block belongs to inheriting classes, not here - move
        if self.size <= 4:
            # Type Descriptor stores no additional data
            td_elem.set("Format", "inline")
        else:
            if self.index >= 0:
                part_fname = "{:s}_{:04d}.{:s}".format(fname_base,self.index,"bin")
            else:
                part_fname = "{:s}.{:s}".format(fname_base,"bin")
            if (self.po.verbose > 2):
                print("{:s}: For Type Descriptor {}, writing BIN file '{}'"\
                  .format(self.vi.src_fname,self.index,os.path.basename(part_fname)))
            bldata = self.getData()
            bldata.read(4) # The data includes 4-byte header
            with open(part_fname, "wb") as part_fh:
                part_fh.write(bldata.read())

            td_elem.set("Format", "bin")
            td_elem.set("File", os.path.basename(part_fname))

    def exportXMLFinish(self, td_elem):
        # Now fat chunk of code for handling Type Descriptor label
        if self.label is not None:
            self.oflags |= TYPEDESC_FLAGS.HasLabel.value
        else:
            self.oflags &= ~TYPEDESC_FLAGS.HasLabel.value
        # While exporting flags and label, mind the export format set by exportXML()
        if td_elem.get("Format") == "bin":
            # For binary format, export only HasLabel flag instead of the actual label; label is in binary data
            exportXMLBitfields(TYPEDESC_FLAGS, td_elem, self.oflags)
        else:
            # For parsed formats, export "Label" property, and get rid of the flag; existence of the "Label" acts as flag
            exportXMLBitfields(TYPEDESC_FLAGS, td_elem, self.oflags, \
              skip_mask=TYPEDESC_FLAGS.HasLabel.value)
            if self.label is not None:
                label_text = self.label.decode(self.vi.textEncoding)
                td_elem.set("Label", "{:s}".format(label_text))
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
        exp_whole_len = self.expectedRSRCSize()
        if (exp_whole_len is not None) and (len(self.raw_data) != exp_whole_len):
            if (self.po.verbose > 1):
                tmp = ""
                if self.otype == TD_FULL_TYPE.Refnum.value:
                    tmp = " RefType {}".format(self.refType())
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x}{} data size {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,tmp,len(self.raw_data),exp_whole_len))
            ret = False
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
          (self.fullType() == TD_FULL_TYPE.FixedPoint))

    def isString(self):
        return ( \
          (self.fullType() == TD_FULL_TYPE.String));
        # looks like these are not counted as strings?
        #  (self.fullType() == TD_FULL_TYPE.CString) or \
        #  (self.fullType() == TD_FULL_TYPE.PasString))

    def isPath(self):
        return ( \
          (self.fullType() == TD_FULL_TYPE.Path))

    def constantSizeFill(self):
        """ If this type has constant-size DataFill, returns that size.

        Gives non-negative integer, or None if the type has no constant
        size DataFill.
        Note: Make sure that DataFill implementation of the type matches
        the return value of this function.
        """
        fullType = self.fullType()
        if fullType in (TD_FULL_TYPE.NumInt8,TD_FULL_TYPE.NumUInt8,TD_FULL_TYPE.UnitUInt8,):
            return 1
        elif fullType in (TD_FULL_TYPE.NumInt16,TD_FULL_TYPE.NumUInt16,TD_FULL_TYPE.UnitUInt16,):
            return 2
        elif fullType in (TD_FULL_TYPE.NumInt32,TD_FULL_TYPE.NumUInt32,TD_FULL_TYPE.UnitUInt32,):
            return 4
        elif fullType in (TD_FULL_TYPE.NumInt64,TD_FULL_TYPE.NumUInt64,):
            return 8
        #TODO some constant size types are missing here
        return None

    def hasClients(self):
        return False

    def clientsEnumerate(self):
        """ Gives enumeration of client TDs.

        To be overloaded in classes for specific TypeDesc types if they
        store sub-TDs.
        """
        return []

    def getClientTypeDescsByType(self):
        """ Gives client TDs put into buckets depending on type.

        To be overloaded in classes for specific TypeDesc types if they
        store sub-TDs.
        """
        out_lists = { 'number': [], 'path': [], 'string': [], 'compound': [], 'other': [] }
        return out_lists

    def __repr__(self):
        d = self.__dict__.copy()
        del d['vi']
        del d['po']
        del d['parsed_data_updated']
        del d['raw_data_updated']
        del d['raw_data']
        if d['topTypeList'] is not None:
            d['topTypeList'] = "PRESENT"
        del d['size']
        from pprint import pformat
        return type(self).__name__ + pformat(d, indent=0, compact=True, width=512)


class TDObjectContainer(TDObject):
    """ Base class for Type Descriptor which contains sub-TDs

    Client TDs can be either nested or indexed. Nested - are stored directly within the
    Container TD, just after container definition. Indexed - are stored in Owning List,
    at given index.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.clients = []

    def parseData(self):
        """ Parse data of specific section and place it as Type Descriptor properties
        """
        needParse = self.needParseData()
        super().parseData()
        if needParse:
            for i, clientTD in enumerate(self.clients):
                if clientTD.index != -1: # this is how we mark nested client
                    continue
                td = clientTD.nested
                td.parseData()
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        for clientTD in self.clients:
            if clientTD.index == -1:
                clientTD.nested.setOwningList(self.topTypeList)
                clientTD.nested.initWithXMLLate()
        pass

    def checkSanity(self):
        ret = True
        # Get Type List for checking non-nested clientTDs
        typeList = None
        if self.topTypeList is not None:
            typeList = self.topTypeList
        else:
            VCTP = self.vi.get('VCTP')
            if VCTP is not None:
                typeList = VCTP.getContent()
        for i, clientTD in enumerate(self.clients):
            if clientTD.index == -1: # Special case this is how we mark nested client
                if clientTD.nested is None:
                    if (self.po.verbose > 1):
                        eprint("{:s}: Warning: TypeDesc {:d} nested sub-type {:d} does not exist"\
                          .format(self.vi.src_fname,self.index,i))
                    ret = False
                elif not clientTD.nested.checkSanity():
                    if (self.po.verbose > 1):
                        eprint("{:s}: Warning: TypeDesc {:d} nested sub-type {:d} failed sanity test"\
                          .format(self.vi.src_fname,self.index,i))
                    ret = False
                pass
            else:
                if clientTD.index < 0:
                    if (self.po.verbose > 1):
                        eprint("{:s}: Warning: TypeDesc {:d} sub-type {:d} references negative TD {:d}"\
                          .format(self.vi.src_fname,self.index,i,clientTD.index))
                    ret = False
                if typeList is not None:
                    if clientTD.index >= len(typeList):
                        if (self.po.verbose > 1):
                            eprint("{:s}: Warning: TypeDesc {:d} sub-type {:d} references outranged TD {:d}"\
                              .format(self.vi.src_fname,self.index,i,clientTD.index))
                        ret = False
                pass
        if not super().checkSanity():
            ret = False
        return ret

    def setOwningList(self, typeList=None):
        """ Sets a list of TDs which owns this TD and all sub-TDs.
        """
        super().setOwningList(typeList)
        for clientTD in self.clients:
            if clientTD.index == -1:
                clientTD.nested.setOwningList(self.topTypeList)

    def hasClients(self):
        return (len(self.clients) > 0)

    def clientsEnumerate(self):
        if self.topTypeList is not None:
            typeList = self.topTypeList
        else:
            VCTP = self.vi.get_or_raise('VCTP')
            typeList = VCTP.getContent()
        out_enum = []
        for i, clientTD in enumerate(self.clients):
            if clientTD.index == -1: # This is how we mark nested client
                td = clientTD.nested
            else:
                td = typeList[clientTD.index].nested
            out_enum.append( (i, clientTD.index, td, clientTD.flags, ) )
        return out_enum

    def clientsRepeatCount(self):
        """ How many times the clients are repeated in this type

        Used for kinds of arrays.
        """
        return 1

    def getClientTypeDescsByType(self):
        self.parseData() # Make sure the block is parsed
        out_lists = { 'number': [], 'path': [], 'string': [], 'compound': [], 'other': [] }
        for cli_idx, td_idx, td_obj, td_flags in self.clientsEnumerate():
            # We will need a list of clients, so might as well parse the Type Descriptor now
            td_obj.parseData()
            if not td_obj.checkSanity():
                if (self.po.verbose > 0):
                    eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} sanity check failed!"\
                      .format(self.vi.src_fname,td_obj.index,td_obj.otype))
            # Add Type Descriptor of this Terminal to list
            if td_obj.isNumber():
                out_lists['number'].append(td_obj)
            elif td_obj.isPath():
                out_lists['path'].append(td_obj)
            elif td_obj.isString():
                out_lists['string'].append(td_obj)
            elif td_obj.hasClients():
                out_lists['compound'].append(td_obj)
            else:
                out_lists['other'].append(td_obj)
            if (self.po.verbose > 2):
                keys = list(out_lists)
                print("enumerating: {}.{} idx={} flags={:09x} type={} TypeDescs: {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d} {:s}={:d}"\
                      .format(self.index, cli_idx, td_idx,  td_flags,\
                        td_obj.fullType().name if isinstance(td_obj.fullType(), enum.IntEnum) else td_obj.fullType(),\
                        keys[0],len(out_lists[keys[0]]),\
                        keys[1],len(out_lists[keys[1]]),\
                        keys[2],len(out_lists[keys[2]]),\
                        keys[3],len(out_lists[keys[3]]),\
                        keys[4],len(out_lists[keys[4]]),\
                      ))
            # Add sub-TD terminals within this TD
            if td_obj.hasClients():
                sub_lists = td_obj.getClientTypeDescsByType()
                for k in out_lists:
                    out_lists[k].extend(sub_lists[k])
        return out_lists

    def parseRSRCNestedTD(self, bldata, tm_flags=0):
        """ Parse RSRC data of a nested Type Descriptor stored within master TD

        This if for parsing client TD which is not in main list of TypeDesc, instead
        being stored directly after main TD. Index -1 is assigned to the TD
        as indication that it is nested and not stored in any consolidated list.
        """
        ver = self.vi.getFileVersion()
        pos = bldata.tell()
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        obj_type, obj_flags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        obj = newTDObject(self.vi, self.blockref, -1, obj_flags, obj_type, self.po)
        bldata.seek(pos)
        obj.setOwningList(self.topTypeList)
        # size of nested TypeDesc is sometimes computed differently than in main TypeDesc
        if isGreaterOrEqVersion(ver, 8,0,0,1):
            # The object length of this nested TypeDesc is 4 bytes larger than real thing.
            norm_obj_len = obj_len-4
        else:
            # In older versions, size was normal.
            norm_obj_len = obj_len
        obj.initWithRSRC(bldata, norm_obj_len)
        clientTD = SimpleNamespace()
        clientTD.index = obj.index # Nested clients have index -1
        clientTD.flags = tm_flags
        clientTD.nested = obj
        return clientTD, obj_len

    def parseRSRCIndexedTD(self, bldata, tm_flags=0):
        clientTD = SimpleNamespace()
        clientTD.index = readVariableSizeFieldU2p2(bldata)
        clientTD.flags = tm_flags
        obj_len = ( 2 if (clientTD.index <= 0x7fff) else 4 )
        return clientTD, obj_len

    def prepareRSRCNestedTD(self, clientTD, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = clientTD.nested.prepareRSRCData(avoid_recompute=avoid_recompute)
        data_buf += clientTD.nested.prepareRSRCDataFinish()

        # size of nested TypeDesc is sometimes computed differently than in main TypeDesc
        if isGreaterOrEqVersion(ver, 8,0,0,1):
            # The object length of this nested TypeDesc is 4 bytes larger than real thing.
            norm_obj_len = len(data_buf) + 8
        else:
            # In older versions, size was normal.
            norm_obj_len = len(data_buf) + 4
        data_head = int(norm_obj_len).to_bytes(2, byteorder='big', signed=False)
        data_head += int(clientTD.nested.oflags).to_bytes(1, byteorder='big', signed=False)
        data_head += int(clientTD.nested.otype).to_bytes(1, byteorder='big', signed=False)

        return data_head + data_buf

    def prepareRSRCIndexedTD(self, clientTD, avoid_recompute=False):
        return prepareVariableSizeFieldU2p2(clientTD.index)

    def expectedRSRCClientTDSize(self, clientTD):
        if clientTD.index == -1:
            # nested expected size already includes header size
            obj_len = clientTD.nested.expectedRSRCSize()
        else:
            obj_len = 2 if clientTD.index <= 0x7FFF else 4
        return obj_len

    def initWithXMLNestedTD(self, td_subelem):
        clientTD = SimpleNamespace()
        clientTD.index = -1
        clientTD.flags = 0
        obj_type = valFromEnumOrIntString(TD_FULL_TYPE, td_subelem.get("Type"))
        obj_flags = importXMLBitfields(TYPEDESC_FLAGS, td_subelem)
        obj = newTDObject(self.vi, self.blockref, clientTD.index, obj_flags, obj_type, self.po)
        clientTD.nested = obj
        obj.initWithXML(td_subelem)
        return clientTD

    def initWithXMLIndexedTD(self, td_subelem):
        clientTD = SimpleNamespace()
        clientTD.index = int(td_subelem.get("TypeID"), 0)
        clientTD.flags = 0
        tmp = td_subelem.get("Flags")
        if tmp is not None:
            clientTD.flags = int(tmp, 0)
        return clientTD

    def initWithXMLAnyClientTD(self, td_subelem):
        if td_subelem.get("TypeID") is not None:
            clientTD = self.initWithXMLIndexedTD(td_subelem)
        elif td_subelem.get("Type") is not None:
            clientTD = self.initWithXMLNestedTD(td_subelem)
        else:
            raise AttributeError("TypeDesc sub-TD lacks mandatory attributes")
        return clientTD

    def exportXMLNestedTD(self, clientTD, td_subelem, cli_fname):
        td_subelem.set("Type", "{:s}".format(stringFromValEnumOrInt(TD_FULL_TYPE, clientTD.nested.otype)))
        td_subelem.set("Nested", "True")
        clientTD.nested.exportXML(td_subelem, cli_fname)
        clientTD.nested.exportXMLFinish(td_subelem)

    def exportXMLIndexedTD(self, clientTD, td_subelem, cli_fname, skip_flags=True):
        td_subelem.set("TypeID", str(clientTD.index))
        if (not skip_flags) or (clientTD.flags != 0):
            td_subelem.set("Flags", "0x{:04X}".format(clientTD.flags))
        pass

    def exportXMLAllClients(self, td_elem, fname_base):
        for i, clientTD in enumerate(self.clients):
            subelem = ET.SubElement(td_elem,"TypeDesc")

            cli_fname = "{:s}_cli{:02d}".format(fname_base,i)
            if clientTD.index == -1:
                self.exportXMLNestedTD(clientTD, subelem, cli_fname)
            else:
                self.exportXMLIndexedTD(clientTD, subelem, cli_fname)
        pass


class TDObjectVoid(TDObject):
    """ Type Descriptor with Void data
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
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, td_elem):
        fmt = td_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(td_elem)

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, td_elem)
        pass

    def exportXML(self, td_elem, fname_base):
        self.parseData()
        # Type Descriptor stores no additional data
        td_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        return ret


class TDObjectBool(TDObjectVoid):
    """ Type Descriptor with Boolean data

    Stores no additional data, so handling is identical to Void TypeDesc.
    """
    pass


class TDObjectLVVariant(TDObjectVoid):
    """ Type Descriptor with data supporting multiple types(variant type)

    Stores no additional data, so handling is identical to Void TypeDesc.
    """
    pass


class TDObjectNumber(TDObject):
    """ Type Descriptor with single number as data

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
        # Create _separate_ empty namespace for each TypeDesc
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
        # Create _separate_ empty namespace for each TypeDesc
        self.values = [SimpleNamespace() for _ in range(count)]
        for i in range(count):
            intval1 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            intval2 = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
            self.values[i].label = "0x{:02X}:0x{:02X}".format(intval1,intval2)
            self.values[i].intval1 = intval1
            self.values[i].intval2 = intval2
        pass

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)
        self.padding1 = b''
        self.values = []
        self.prop1 = None

        if self.isEnum():
            self.parseRSRCEnumAttr(bldata)

        if self.isPhys():
            self.parseRSRCUnitsAttr(bldata)

        if isGreaterOrEqVersion(ver, 8,0,0,1):
            self.prop1 = int.from_bytes(bldata.read(1), byteorder='big', signed=False)
        # No more data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCEnumAttr(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.values)).to_bytes(2, byteorder='big', signed=False)
        for value in self.values:
            data_buf += preparePStr(value.label, 1, self.po)
        if len(data_buf) % 2 > 0:
            padding_len = 2 - (len(data_buf) % 2)
            data_buf += (b'\0' * padding_len)
        return data_buf

    def prepareRSRCUnitsAttr(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(len(self.values)).to_bytes(2, byteorder='big', signed=False)
        for i, value in enumerate(self.values):
            data_buf += int(value.intval1).to_bytes(2, byteorder='big', signed=False)
            data_buf += int(value.intval2).to_bytes(2, byteorder='big', signed=False)
            if (self.po.verbose > 2):
                print("{:s}: TD {:d} type 0x{:02x} Units Attr {} are 0x{:02X} 0x{:02X}"\
                  .format(self.vi.src_fname,self.index,self.otype,i,value.intval1,value.intval2))
        return data_buf

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = b''

        if self.isEnum():
            data_buf += self.prepareRSRCEnumAttr(avoid_recompute=avoid_recompute)

        if self.isPhys():
            data_buf += self.prepareRSRCUnitsAttr(avoid_recompute=avoid_recompute)

        if isGreaterOrEqVersion(ver, 8,0,0,1) and self.prop1 is not None:
            data_buf += int(self.prop1).to_bytes(1, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        if self.isEnum():
            exp_whole_len += 2 + sum((1+len(v.label)) for v in self.values)
            if exp_whole_len % 2 > 0:
                exp_whole_len += 2 - (exp_whole_len % 2)
        if self.isPhys():
            exp_whole_len = 2 + (2+2) * len(self.values)
        if self.prop1 is not None:
            exp_whole_len += 1
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXMLEnumAttr(self, td_elem):
        for subelem in td_elem:
            if (subelem.tag == "EnumLabel"):
                value = SimpleNamespace()
                label_str = subelem.text
                if label_str is None:
                    label_str = ''
                value.label = label_str.encode(self.vi.textEncoding)
                value.intval1 = None
                value.intval2 = None
                self.values.append(value)
            else:
                raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                  .format(subelem.tag))
        pass

    def initWithXMLUnitsAttr(self, td_elem):
        for subelem in td_elem:
            if (subelem.tag == "PhysUnit"):
                value = SimpleNamespace()
                value.intval1 = int(subelem.get("Val1"), 0)
                value.intval2 = int(subelem.get("Val2"), 0)
                value.label = "0x{:02X}:0x{:02X}".format(value.intval1,value.intval2)
                if (self.po.verbose > 2):
                    print("{:s}: TD {:d} type 0x{:02x} Units Attr {} are 0x{:02X} 0x{:02X}"\
                      .format(self.vi.src_fname,self.index,self.otype,i,value.intval1,value.intval2))
                self.values.append(value)
            else:
                raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                  .format(subelem.tag))
        pass

    def initWithXML(self, td_elem):
        self.prop1 = None
        self.padding1 = b''
        self.values = []

        fmt = td_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(td_elem)

            tmp = td_elem.get("Prop1")
            if tmp is not None:
                self.prop1 = int(tmp, 0)

            if self.isEnum():
                self.initWithXMLEnumAttr(td_elem)
            if self.isPhys():
                self.initWithXMLUnitsAttr(td_elem)

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, td_elem)
        pass

    def exportXMLEnumAttr(self, td_elem, fname_base):
        for i, value in enumerate(self.values):
            subelem = ET.SubElement(td_elem,"EnumLabel")

            label_str = value.label.decode(self.vi.textEncoding)
            subelem.text = label_str
        pass

    def exportXMLUnitsAttr(self, td_elem, fname_base):
        for i, value in enumerate(self.values):
            subelem = ET.SubElement(td_elem,"PhysUnit")

            subelem.set("Val1", "{:d}".format(value.intval1))
            subelem.set("Val2", "{:d}".format(value.intval2))
        pass

    def exportXML(self, td_elem, fname_base):
        self.parseData()
        if self.prop1 is not None:
            td_elem.set("Prop1", "{:d}".format(self.prop1))
        if self.isEnum():
            self.exportXMLEnumAttr(td_elem, fname_base)
        if self.isPhys():
            self.exportXMLUnitsAttr(td_elem, fname_base)
        td_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        if (self.prop1 & ~1) != 0: # 0 or 1
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02X} property1 {:d}, expected 1 bit value"\
                  .format(self.vi.src_fname,self.index,self.otype,self.prop1))
            ret = False
        if (self.isEnum() or self.isPhys()):
            if len(self.values) < 1:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02X} has empty values list"\
                      .format(self.vi.src_fname,self.index,self.otype))
                ret = False
        if len(self.padding1) > 0 and (self.padding1 != b'\0'):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02X} padding1 {}, expected zeros"\
                  .format(self.vi.src_fname,self.index,self.otype,self.padding1))
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
    """ Type Descriptor with C String data

    Stores no additional data, so handling is identical to Void TypeDesc.
    """
    pass


class TDObjectPasString(TDObjectVoid):
    """ Type Descriptor with Pascal String data

    Stores no additional data, so handling is identical to Void TypeDesc.
    """
    pass


class TDObjectTag(TDObject):
    """ Type Descriptor with Tag data
    """
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
            obj = LVclasses.LVVariant(0, self.vi, self.blockref, self.po)
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
        data_buf += int(self.prop1).to_bytes(4, byteorder='big', signed=False)
        data_buf += int(self.tagType).to_bytes(2, byteorder='big', signed=False)

        if isGreaterOrEqVersion(ver, 8,2,1) and \
          (isSmallerVersion(ver, 8,2,2) or isGreaterOrEqVersion(ver, 8,5,1)):
            data_buf += self.variobj.prepareRSRCData(avoid_recompute=avoid_recompute)

        if (self.tagType == TAG_TYPE.UserDefined.value) and isGreaterOrEqVersion(ver, 8,1,1):
            strlen = len(self.ident)
            data_buf += int(strlen).to_bytes(1, byteorder='big', signed=False)
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
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, td_elem):
        fmt = td_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(td_elem)

            self.ident = None
            self.variobj = None
            self.prop1 = int(td_elem.get("Prop1"), 0)
            self.tagType = valFromEnumOrIntString(TAG_TYPE, td_elem.get("TagType"))

            for subelem in td_elem:
                if (subelem.tag == "Ident"):
                    identStr = subelem.text
                    if identStr is not None:
                        self.ident = identStr.encode(self.vi.textEncoding)
                elif (subelem.tag == "LVVariant"):
                    i = int(subelem.get("Index"), 0)
                    obj = LVclasses.LVVariant(i, self.vi, self.blockref, self.po)
                    obj.initWithXML(subelem)
                    self.variobj = obj
                else:
                    raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                      .format(subelem.tag))

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, td_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        if self.variobj is not None:
            self.variobj.initWithXMLLate()
        pass

    def exportXML(self, td_elem, fname_base):
        self.parseData()

        td_elem.set("Prop1", "0x{:X}".format(self.prop1))
        td_elem.set("TagType", stringFromValEnumOrInt(TAG_TYPE, self.tagType))

        if self.ident is not None:
            subelem = ET.SubElement(td_elem,"Ident")
            subelem.text = self.ident.decode(self.vi.textEncoding)

        if self.variobj is not None:
            obj = self.variobj
            i = 0
            subelem = ET.SubElement(td_elem,"LVObject") # Export function from the object may overwrite the tag

            subelem.set("Index", "{:d}".format(i))

            if self.index >= 0:
                part_fname = "{:s}_{:04d}_lvo{:02d}".format(fname_base,self.index,i)
            else:
                part_fname = "{:s}_lvo{:02d}".format(fname_base,i)
            obj.exportXML(subelem, part_fname)

        td_elem.set("Format", "inline")

    def checkSanity(self):
        ver = self.vi.getFileVersion()
        ret = super().checkSanity()
        if self.prop1 != 0xFFFFFFFF:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} property1 0x{:x}, expected 0x{:x}"\
                  .format(self.vi.src_fname,self.index,self.otype,self.prop1,0xFFFFFFFF))
            ret = False
        if isGreaterOrEqVersion(ver, 8,2,1) and \
          (isSmallerVersion(ver, 8,2,2) or isGreaterOrEqVersion(ver, 8,5,1)):
            if self.variobj is None:
                ret = False
            elif not self.variobj.checkSanity():
                ret = False
        else:
            if self.variobj is not None:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} Variant object present, but LV version with no support"\
                      .format(self.vi.src_fname,self.index,self.otype))
                ret = False
        return ret


class TDObjectBlob(TDObject):
    """ Type Descriptor with generic blob of data
    """
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
        data_buf += int(self.prop1).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 4
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, td_elem):
        fmt = td_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(td_elem)
            self.prop1 = int(td_elem.get("Prop1"), 0)

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, td_elem)
        pass

    def exportXML(self, td_elem, fname_base):
        self.parseData()
        td_elem.set("Prop1", "0x{:X}".format(self.prop1))
        td_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        if self.otype not in (TD_FULL_TYPE.PolyVI, TD_FULL_TYPE.Block,):
            if self.prop1 != 0xFFFFFFFF:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} property1 0x{:x}, expected 0x{:x}"\
                      .format(self.vi.src_fname,self.index,self.otype,self.prop1,0xFFFFFFFF))
                ret = False
        return ret


class TDObjectNumberPtr(TDObjectVoid):
    """ Type Descriptor with Number Pointer as data

    Stores no additional data, so handling is identical to Void TypeDesc.
    """
    pass

class TDObjectString(TDObjectBlob):
    """ Type Descriptor with String data
    """
    pass


class TDObjectPath(TDObjectBlob):
    """ Type Descriptor with Path Object as data
    """
    pass


class TDObjectPicture(TDObjectBlob):
    """ Type Descriptor with Picture data
    """
    pass


class TDObjectSubString(TDObjectBlob):
    """ Type Descriptor with sub-string data
    """
    pass


class TDObjectPolyVI(TDObjectBlob):
    """ Type Descriptor with PolymorphicVI data
    """
    pass


class TDObjectFunction(TDObjectContainer):
    """ Type Descriptor with Function data
    """
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
        # Create _separate_ empty namespace for each TypeDesc
        self.clients = []
        for i in range(count):
            clientTD, cli_len = self.parseRSRCIndexedTD(bldata)
            self.clients.append(clientTD)
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
            # If the flag is set, then the last sub-type is special - comes from here, not the standard list
            clientTD, cli_len = self.parseRSRCIndexedTD(bldata)
            clientTD.thrallSources = []
            self.clients.append(clientTD)

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
            # Store last sub-type separately, remove it from normal list
            spec_cli = clients.pop()

        data_buf += prepareVariableSizeFieldU2p2(len(clients))
        for clientTD in clients:
            data_buf += self.prepareRSRCIndexedTD(clientTD, avoid_recompute=avoid_recompute)
        # end of MultiContainer part
        data_buf += int(self.fflags).to_bytes(2, byteorder='big', signed=False)
        data_buf += int(self.pattern).to_bytes(2, byteorder='big', signed=False)

        if isGreaterOrEqVersion(ver, 10,0,0,stage="alpha"):
            for clientTD in clients:
                data_buf += int(clientTD.flags).to_bytes(4, byteorder='big', signed=False)
        else:
            for clientTD in clients:
                data_buf += int(clientTD.flags).to_bytes(2, byteorder='big', signed=False)

        if isGreaterOrEqVersion(ver, 8,0,0,stage="beta"):
            data_buf += int(self.hasThrall).to_bytes(2, byteorder='big', signed=False)
            if self.hasThrall != 0:
                for clientTD in clients:
                    for k in clientTD.thrallSources:
                        if isGreaterOrEqVersion(ver, 8,2,0,stage="beta"):
                            k = k + 1
                        data_buf += int(k).to_bytes(1, byteorder='big', signed=False)
                    data_buf += int(0).to_bytes(1, byteorder='big')

        if (self.fflags & 0x0800) != 0:
            data_buf += int(self.field6).to_bytes(4, byteorder='big', signed=False)
            data_buf += int(self.field7).to_bytes(4, byteorder='big', signed=False)
        if spec_cli is not None:
            data_buf += self.prepareRSRCIndexedTD(spec_cli, avoid_recompute=avoid_recompute)

        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        clients = self.clients.copy()
        exp_whole_len = 4
        spec_cli = None
        if (self.fflags & 0x8000) != 0:
            spec_cli = clients.pop()
        exp_whole_len += 2 if len(clients) <= 0x7FFF else 4
        for clientTD in clients:
            exp_whole_len += self.expectedRSRCClientTDSize(clientTD)
        exp_whole_len += 2 + 2

        if isGreaterOrEqVersion(ver, 10,0,0,stage="alpha"):
            exp_whole_len += 4 * len(clients)
        else:
            exp_whole_len += 2 * len(clients)

        if isGreaterOrEqVersion(ver, 8,0,0,stage="beta"):
            exp_whole_len += 2
            if self.hasThrall != 0:
                for clientTD in clients:
                    exp_whole_len += 1 * len(clientTD.thrallSources)
                    exp_whole_len += 1

        if (self.fflags & 0x0800) != 0:
            exp_whole_len += 8
        if spec_cli is not None:
            exp_whole_len += self.expectedRSRCClientTDSize(spec_cli)

        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
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
                if (subelem.tag == "TypeDesc"):
                    clientTD = self.initWithXMLAnyClientTD(subelem)
                    clientTD.thrallSources = []
                    for sub_subelem in subelem:
                        if (sub_subelem.tag == "ThrallSources"):
                            clientTD.thrallSources += [int(itm,0) for itm in sub_subelem.text.split()]
                        else:
                            raise AttributeError("TypeDesc sub-type contains unexpected tag '{}'"\
                              .format(subelem.tag))
                    self.clients.append(clientTD)
                else:
                    raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                      .format(subelem.tag))

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXMLAllClients(self, td_elem, fname_base):
        for i, clientTD in enumerate(self.clients):
            subelem = ET.SubElement(td_elem,"TypeDesc")

            cli_fname = "{:s}_cli{:02d}".format(fname_base,i)
            if clientTD.index == -1:
                self.exportXMLNestedTD(clientTD, subelem, cli_fname)
            else:
                self.exportXMLIndexedTD(clientTD, subelem, cli_fname, skip_flags=False)

            if len(clientTD.thrallSources) > 0:
                strlist = ""
                for k, val in enumerate(clientTD.thrallSources):
                    strlist += " {:3d}".format(val)

                sub_subelem = ET.SubElement(subelem,"ThrallSources")
                sub_subelem.text = strlist
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

        self.exportXMLAllClients(conn_elem, fname_base)

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        if (len(self.clients) > 125):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} clients count {:d}, expected below {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),125+1))
            ret = False
        return ret


class TDObjectTypeDef(TDObjectContainer):
    """ Type Descriptor which stores type definition

    TypeDescs of this type have a special support in LabView code, where type data
    is replaced by the data from nested TD. But we shouldn't need it here.
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.flag1 = 0
        self.labels = []

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
        self.clients = [ ]
        # In "Vi Explorer" code, the length value of this object is treated differently
        # (decreased by 4); not sure if this is correct and an issue here
        if True:
            clientTD, cli_len = self.parseRSRCNestedTD(bldata)
            self.clients.append(clientTD)
            clientTD.nested.setOwningList(self.topTypeList)
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            ver = decodeVersion(0x09000000)
        data_buf = b''
        data_buf += int(self.flag1).to_bytes(4, byteorder='big', signed=False)
        if isGreaterOrEqVersion(ver, 8,0,0,4):
            data_buf += prepareQualifiedName(self.labels, self.po)
        else:
            data_buf += preparePStr(b'/'.join(self.labels), 2, self.po)
        if len(self.clients) != 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} has unexpacted amount of clients; should have 1"\
                  .format(self.vi.src_fname,self.index,self.otype))
        for clientTD in self.clients:
            if clientTD.index == -1:
                data_buf += self.prepareRSRCNestedTD(clientTD, avoid_recompute=avoid_recompute)
            else:
                data_buf += self.prepareRSRCIndexedTD(clientTD, avoid_recompute=avoid_recompute)

        return data_buf

    def expectedRSRCSize(self):
        ver = self.vi.getFileVersion()
        exp_whole_len = 4
        exp_whole_len += 4
        if isGreaterOrEqVersion(ver, 8,0,0,4):
            # QualifiedName
            exp_whole_len += 4 + sum((1+len(s)) for s in self.labels)
        else:
            exp_whole_len += sum((1+len(s)) for s in self.labels)
            if exp_whole_len % 2 > 0: # Include padding
                exp_whole_len += 2 - (exp_whole_len % 2)
        for clientTD in self.clients:
            exp_whole_len += self.expectedRSRCClientTDSize(clientTD)
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.flag1 = int(conn_elem.get("Flag1"), 0)

            self.labels = []
            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "TypeDesc"):
                    clientTD = self.initWithXMLNestedTD(subelem)
                    self.clients.append(clientTD)
                elif (subelem.tag == "Label"):
                    label = subelem.get("Text").encode(self.vi.textEncoding)
                    self.labels.append(label)
                else:
                    raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                      .format(subelem.tag))

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        conn_elem.set("Flag1", "0x{:X}".format(self.flag1))

        self.exportXMLAllClients(conn_elem, fname_base)

        for i, label in enumerate(self.labels):
            subelem = ET.SubElement(conn_elem,"Label")

            label_text = label.decode(self.vi.textEncoding)
            subelem.set("Text", "{:s}".format(label_text))

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        if (len(self.clients) != 1):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} clients count {:d}, expected {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),1))
            ret = False
        for i, clientTD in enumerate(self.clients):
            if clientTD.index != -1:
                if (self.po.verbose > 1):
                    eprint("{:s}: Warning: TypeDesc {:d} expected to have nested client"\
                      .format(self.vi.src_fname,i))
                ret = False
            pass
        return ret


class TDObjectArray(TDObjectContainer):
    """ Type Descriptor with Multidimentional Array data
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.dimensions = [ ]

    def clientsRepeatCount(self):
        """ How many times the clients are repeated in this type

        Used for kinds of arrays. Returns -1 if the size is dynamic.
        """
        totItems = 1
        for i, dim in enumerate(self.dimensions):
            if (dim.flags == 0xFF) and (dim.fixedSize == 0x00FFFFFF):
                return -1 # dynamic size
            totItems *= dim.fixedSize
        return totItems

    def parseRSRCData(self, bldata):
        ver = self.vi.getFileVersion()
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        ndimensions = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.dimensions = [SimpleNamespace() for _ in range(ndimensions)]
        for dim in self.dimensions:
            flags = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
            dim.flags = flags >> 24
            dim.fixedSize = flags & 0x00FFFFFF

        self.clients = [ ]
        if isGreaterOrEqVersion(ver, 8,0,0,1):
            for i in range(1):
                clientTD, cli_len = self.parseRSRCIndexedTD(bldata)
                self.clients.append(clientTD)
        else:
            for i in range(1):
                clientTD, cli_len = self.parseRSRCNestedTD(bldata)
                self.clients.append(clientTD)

        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        if not avoid_recompute:
            ver = self.vi.getFileVersion()
        else:
            if (len(self.clients) > 0) and (self.clients[0].index == -1):
                ver = decodeVersion(0x07000000)
            else:
                ver = decodeVersion(0x09000000)
        data_buf = b''
        data_buf += int(len(self.dimensions)).to_bytes(2, byteorder='big', signed=False)
        for dim in self.dimensions:
            flags = (dim.flags << 24) | dim.fixedSize
            data_buf += int(flags).to_bytes(4, byteorder='big', signed=False)
        if len(self.clients) != 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} has unexpacted amount of clients; should have 1"\
                  .format(self.vi.src_fname,self.index,self.otype))
        if isGreaterOrEqVersion(ver, 8,0,0,1):
            for clientTD in self.clients:
                if clientTD.index == -1:
                    raise AttributeError("Type Descriptor contains nested client but LV8+ format is in use")
                data_buf += self.prepareRSRCIndexedTD(clientTD, avoid_recompute=avoid_recompute)
        else:
            for clientTD in self.clients:
                if clientTD.index != -1:
                    raise AttributeError("Type Descriptor contains indexed client but pre-LV8 format is in use")
                data_buf += self.prepareRSRCNestedTD(clientTD, avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2 + 4 * len(self.dimensions)
        for clientTD in self.clients:
            exp_whole_len += self.expectedRSRCClientTDSize(clientTD)
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)

            self.dimensions = []
            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "Dimension"):
                    dim = SimpleNamespace()
                    dim.flags = int(subelem.get("Flags"), 0)
                    dim.fixedSize = int(subelem.get("FixedSize"), 0)
                    self.dimensions.append(dim)
                elif (subelem.tag == "TypeDesc"):
                    clientTD = self.initWithXMLAnyClientTD(subelem)
                    self.clients.append(clientTD)
                else:
                    raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                      .format(subelem.tag))

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        for i, dim in enumerate(self.dimensions):
            subelem = ET.SubElement(conn_elem,"Dimension")

            subelem.set("Flags", "0x{:04X}".format(dim.flags))
            subelem.set("FixedSize", "0x{:04X}".format(dim.fixedSize))

        self.exportXMLAllClients(conn_elem, fname_base)

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        if len(self.dimensions) > 64:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} has {} dimensions, expected below {}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.dimensions),64))
            ret = False
        if len(self.clients) != 1:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} has {} clients, expected exactly {}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),1))
            ret = False
        return ret


class TDObjectBlock(TDObjectContainer):
    """ Type Descriptor with Block based data

    Inherits from Container only because of further inheriting classes.
    """
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
        data_buf += int(self.blkSize).to_bytes(4, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += self.expectedRSRCDataSize()
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def expectedRSRCDataSize(self):
        exp_whole_len = 0
        exp_whole_len += 4
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
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
        ret = super().checkSanity()
        return ret


class TDObjectAlignedBlock(TDObjectBlock):
    """ Type Descriptor with Aligned Block data
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.clients = []
        self.blkSize = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        for i in range(1):
            clientTD, cli_len = self.parseRSRCIndexedTD(bldata)
            self.clients.append(clientTD)

        # No more known data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.blkSize).to_bytes(4, byteorder='big', signed=False)
        for clientTD in self.clients:
            data_buf += self.prepareRSRCIndexedTD(clientTD, avoid_recompute=avoid_recompute)
            break # only one client is supported
        return data_buf

    def expectedRSRCDataSize(self):
        exp_whole_len = 0
        exp_whole_len += 4
        for clientTD in self.clients:
            exp_whole_len += self.expectedRSRCClientTDSize(clientTD)
            break # only one sub-type is valid
        return exp_whole_len

    def initWithXMLInlineData(self, conn_elem):
        self.clients = []
        self.blkSize = int(conn_elem.get("BlockSize"), 0)

        for subelem in conn_elem:
            if (subelem.tag == "TypeDesc"):
                clientTD = self.initWithXMLAnyClientTD(subelem)
                self.clients.append(clientTD)
            else:
                raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                  .format(subelem.tag))
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()
        conn_elem.set("BlockSize", "0x{:X}".format(self.blkSize))

        self.exportXMLAllClients(conn_elem, fname_base)

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        return ret


class TDObjectRepeatedBlock(TDObjectContainer):
    """ Type Descriptor with data consisting of repeated Block
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.numRepeats = 0
        self.dfComments = {}

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.clients = []
        self.numRepeats = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        for i in range(1):
            clientTD, cli_len = self.parseRSRCIndexedTD(bldata)
            self.clients.append(clientTD)
        # No more known data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.numRepeats).to_bytes(4, byteorder='big', signed=False)
        for clientTD in self.clients:
            data_buf += self.prepareRSRCIndexedTD(clientTD, avoid_recompute=avoid_recompute)
            break # only one sub-type is supported
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 4
        for clientTD in self.clients:
            exp_whole_len += self.expectedRSRCClientTDSize(clientTD)
            break # only one sub-type is valid
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXMLInlineData(self, conn_elem):
        self.clients = []
        self.numRepeats = int(conn_elem.get("NumRepeats"), 0)

        for subelem in conn_elem:
            if (subelem.tag == "TypeDesc"):
                clientTD = self.initWithXMLAnyClientTD(subelem)
                self.clients.append(clientTD)
            else:
                raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                  .format(subelem.tag))
        pass

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
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

        self.exportXMLAllClients(conn_elem, fname_base)

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        return ret

    def setDataFillComments(self, dfComments):
        """ Sets list of comments which will describe Data Fill elements in XML
        """
        self.dfComments = dfComments

    def getNumRepeats(self):
        self.parseData()
        return self.numRepeats


class TDObjectRef(TDObjectContainer):
    """ Type Descriptor with Reference data
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.reftype = int(REFNUM_TYPE.Generic)
        self.ref_obj = None
        self.items = []
        self.objects = []

    def setOwningList(self, typeList=None):
        super().setOwningList(typeList)
        #if self.ref_obj is not None:
        #    self.ref_obj.setOwningList(self.topTypeList)

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.reftype = int.from_bytes(bldata.read(2), byteorder='big', signed=False)
        self.ref_obj = LVdatatyperef.newTDObjectRef(self.vi, self.blockref, self, self.reftype, self.po)
        if self.ref_obj is not None:
            if (self.po.verbose > 2):
                print("{:s}: TD {:d} type 0x{:02x}, has ref_type=0x{:02X} class {:s}"\
                  .format(self.vi.src_fname,self.index,self.otype,self.reftype,type(self.ref_obj).__name__))
            #self.ref_obj.setOwningList(self.topTypeList)
            self.ref_obj.parseRSRCData(bldata)
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += int(self.reftype).to_bytes(2, byteorder='big', signed=False)
        if self.ref_obj is not None:
            data_buf += self.ref_obj.prepareRSRCData(avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2
        if self.ref_obj is not None:
            ref_obj_len = self.ref_obj.expectedRSRCSize()
            if ref_obj_len is None:
                return None
            exp_whole_len += ref_obj_len
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.reftype = valFromEnumOrIntString(REFNUM_TYPE, conn_elem.get("RefType"))

            self.ref_obj = LVdatatyperef.newTDObjectRef(self.vi, self.blockref, self, self.reftype, self.po)
            if self.ref_obj is not None:
                if (self.po.verbose > 2):
                    print("{:s}: TD {:d} type 0x{:02x}, has ref_type=0x{:02X} class {:s}"\
                      .format(self.vi.src_fname,self.index,self.otype,self.reftype,type(self.ref_obj).__name__))
                self.ref_obj.initWithXML(conn_elem)

            self.clients = []
            self.items = []
            for subelem in conn_elem:
                if (subelem.tag == "TypeDesc"):
                    clientTD = self.initWithXMLAnyClientTD(subelem)
                    if self.ref_obj is not None:
                        self.ref_obj.initWithXMLClient(clientTD, subelem)
                    self.clients.append(clientTD)
                elif (subelem.tag == "Item"):
                    item = SimpleNamespace()
                    if self.ref_obj is not None:
                        self.ref_obj.initWithXMLItem(item, subelem)
                    self.items.append(item)
                elif (subelem.tag == "LVVariant"):
                    i = int(subelem.get("Index"), 0)
                    obj = LVclasses.LVVariant(i, self.vi, self.blockref, self.po)
                    # Grow the list if needed (the objects may be in wrong order)
                    if i >= len(self.objects):
                        self.objects.extend([None] * (i - len(self.objects) + 1))
                    obj.initWithXML(subelem)
                    self.objects[i] = obj
                else:
                    raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                      .format(subelem.tag))

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def initWithXMLLate(self):
        super().initWithXMLLate()
        #if self.ref_obj is not None:
        #        self.ref_obj.setOwningList(self.topTypeList) # currently refnums have no setOwningList
        #    self.ref_obj.initWithXMLLate() # currently refnums have no initWithXMLLate
        for obj in self.objects:
            obj.initWithXMLLate()
        pass

    def exportXMLAllClients(self, td_elem, fname_base):
        for i, clientTD in enumerate(self.clients):
            subelem = ET.SubElement(td_elem,"TypeDesc")

            cli_fname = "{:s}_cli{:02d}".format(fname_base,i)
            if clientTD.index == -1:
                self.exportXMLNestedTD(clientTD, subelem, cli_fname)
            else:
                self.exportXMLIndexedTD(clientTD, subelem, cli_fname)

            if self.ref_obj is not None:
                self.ref_obj.exportXMLClient(clientTD, subelem, fname_base)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        conn_elem.set("RefType", stringFromValEnumOrInt(REFNUM_TYPE, self.reftype))
        if self.ref_obj is not None:
            self.ref_obj.exportXML(conn_elem, fname_base)

        self.exportXMLAllClients(conn_elem, fname_base)

        for i, item in enumerate(self.items):
            subelem = ET.SubElement(conn_elem,"Item")

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
        ret = super().checkSanity()
        if self.ref_obj is not None:
            if not self.ref_obj.checkSanity():
                ret = False
        return ret

    def refType(self):
        if self.reftype not in set(item.value for item in REFNUM_TYPE):
            return self.reftype
        return REFNUM_TYPE(self.reftype)


class TDObjectCluster(TDObjectContainer):
    """ Type Descriptor which Clusters together other TDs into a struct
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.dfComments = {}

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        count = readVariableSizeFieldU2p2(bldata)
        # Create _separate_ empty namespace for each TypeDesc
        self.clients = []
        for i in range(count):
            clientTD, cli_len = self.parseRSRCIndexedTD(bldata)
            self.clients.append(clientTD)
        # No more data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        data_buf += len(self.clients).to_bytes(2, byteorder='big', signed=False)
        for clientTD in self.clients:
            data_buf += self.prepareRSRCIndexedTD(clientTD, avoid_recompute=avoid_recompute)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2
        for clientTD in self.clients:
            exp_whole_len += self.expectedRSRCClientTDSize(clientTD)
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)

            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "TypeDesc"):
                    clientTD = self.initWithXMLAnyClientTD(subelem)
                    self.clients.append(clientTD)
                else:
                    raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                      .format(subelem.tag))

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        self.exportXMLAllClients(conn_elem, fname_base)

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        if len(self.clients) > 500:
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} has {:d} clients, expected below {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),500+1))
            ret = False
        return ret

    def setDataFillComments(self, dfComments):
        """ Sets list of comments which will describe Data Fill elements in XML
        """
        self.dfComments = dfComments


class TDObjectMeasureData(TDObject):
    """ Type Descriptor with Measurement data
    """
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
        data_buf += int(self.flavor).to_bytes(2, byteorder='big', signed=False)
        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        exp_whole_len += 2
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
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
        ret = super().checkSanity()
        if self.flavor > 127: # Not sure how many cluster formats are there
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} flavor {:d}, expected below {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,self.flavor,127+1))
            ret = False
        return ret

    def dtFlavor(self):
        if self.flavor not in set(item.value for item in MEASURE_DATA_FLAVOR):
            return self.flavor
        return MEASURE_DATA_FLAVOR(self.flavor)


class TDObjectFixedPoint(TDObject):
    """ Type Descriptor with Filex Point Number data
    """
    def __init__(self, *args):
        super().__init__(*args)
        self.rangeFormat = 0
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
        data_buf += int(field1C).to_bytes(2, byteorder='big', signed=False)
        data_buf += int(self.field1E).to_bytes(2, byteorder='big', signed=False)
        data_buf += int(self.field20).to_bytes(4, byteorder='big', signed=False)

        for i, rang in enumerate(self.ranges):
            if self.rangeFormat == 0:
                data_buf += struct.pack('>d', rang.value)
            elif self.rangeFormat == 1:
                if (self.field1E > 0x40) or (self.dataVersion > 0):
                    data_buf += int(rang.prop1).to_bytes(2, byteorder='big', signed=False)
                    data_buf += int(rang.prop2).to_bytes(2, byteorder='big', signed=False)
                    data_buf += int(rang.prop3).to_bytes(4, byteorder='big', signed=True)
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
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
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

                    rang.value = stringUnequivocalToNumeric(subelem.text, TD_FULL_TYPE.NumFloat64)

                    self.ranges.append(rang)
                else:
                    raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                      .format(subelem.tag))

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

            if self.rangeFormat == 0:
                subelem.text = numericToStringUnequivocal(rang.value, TD_FULL_TYPE.NumFloat64)
            elif self.rangeFormat == 1:
                if (self.field1E > 0x40) or (self.dataVersion > 0):
                    subelem.set("Prop1", "{:d}".format(rang.prop1))
                    subelem.set("Prop2", "{:d}".format(rang.prop2))
                    subelem.set("Prop3", "{:d}".format(rang.prop3))
                subelem.text = numericToStringUnequivocal(rang.value, TD_FULL_TYPE.NumFloat64)
            pass

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        return ret

class TDObjectSingleContainer(TDObjectContainer):
    """ Type Descriptor which is container for one child TD
    """
    def __init__(self, *args):
        super().__init__(*args)

    def parseRSRCData(self, bldata):
        # Fields oflags,otype are set at constructor, but no harm in setting them again
        self.otype, self.oflags, obj_len = TDObject.parseRSRCDataHeader(bldata)

        self.clients = []
        for i in range(1):
            clientTD, cli_len = self.parseRSRCIndexedTD(bldata)
            self.clients.append(clientTD)

        # No more data inside
        self.parseRSRCDataFinish(bldata)

    def prepareRSRCData(self, avoid_recompute=False):
        data_buf = b''
        for clientTD in self.clients:
            data_buf += self.prepareRSRCIndexedTD(clientTD, avoid_recompute=avoid_recompute)
            break # only one sub-type is supported

        return data_buf

    def expectedRSRCSize(self):
        exp_whole_len = 4
        for clientTD in self.clients:
            exp_whole_len += self.expectedRSRCClientTDSize(clientTD)
            break # only one sub-type is valid
        exp_whole_len += self.expectedRSRCLabelSize()
        return exp_whole_len

    def initWithXML(self, conn_elem):
        fmt = conn_elem.get("Format")
        if fmt == "inline": # Format="inline" - the content is stored as subtree of this xml
            if (self.po.verbose > 2):
                print("{:s}: For TypeDesc {:d} type 0x{:02x}, reading inline XML data"\
                  .format(self.vi.src_fname,self.index,self.otype))

            self.initWithXMLInlineStart(conn_elem)
            self.clients = []
            for subelem in conn_elem:
                if (subelem.tag == "TypeDesc"):
                    clientTD = self.initWithXMLAnyClientTD(subelem)
                    self.clients.append(clientTD)
                else:
                    raise AttributeError("Type Descriptor contains unexpected tag '{}'"\
                      .format(subelem.tag))

            self.updateData(avoid_recompute=True)

        else:
            TDObject.initWithXML(self, conn_elem)
        pass

    def exportXML(self, conn_elem, fname_base):
        self.parseData()

        self.exportXMLAllClients(conn_elem, fname_base)

        conn_elem.set("Format", "inline")

    def checkSanity(self):
        ret = super().checkSanity()
        if (len(self.clients) != 1):
            if (self.po.verbose > 1):
                eprint("{:s}: Warning: TypeDesc {:d} type 0x{:02x} clients count {:d}, expected exactly {:d}"\
                  .format(self.vi.src_fname,self.index,self.otype,len(self.clients),1))
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


def newErrorCluster(vi, blockref, idx, obj_flags, po):
    """ Error information is transferred in a specific Cluster
    """
    # Content (fields) of the error cluster
    tdList = []

    tdErrEnt = SimpleNamespace() # error status
    tdErrEnt.index = -1
    tdErrEnt.flags = 0
    tdErrEnt.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.Boolean, po)
    tdList.append(tdErrEnt)

    tdErrEnt = SimpleNamespace() # error code
    tdErrEnt.index = -1
    tdErrEnt.flags = 0
    tdErrEnt.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.NumInt32, po)
    tdList.append(tdErrEnt)

    tdErrEnt = SimpleNamespace() # error source
    tdErrEnt.index = -1
    tdErrEnt.flags = 0
    tdErrEnt.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.String, po)
    tdList.append(tdErrEnt)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, blockref, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster

def newDigitalTableCluster(vi, blockref, idx, obj_flags, po):
    """ The DigitalTable is a Cluster with specific things inside
    """
    # make list of fields
    tdList = []

    tdDigTabEnt = SimpleNamespace() # DigitalTable transitions
    tdDigTabEnt.index = -1
    tdDigTabEnt.flags = 0
    tdDigTabEnt.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.Array, po)
    tdDigTabEnt.nested.dimensions = [SimpleNamespace() for _ in range(1)]
    for dim in tdDigTabEnt.nested.dimensions:
        dim.flags = 0
        dim.fixedSize = -1
    tdDigTabEnt.nested.clients = [ SimpleNamespace() ]
    for client in tdDigTabEnt.nested.clients:
        cli_flags = 0
        client.index = -1
        client.flags = 0
        client.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.NumUInt32, po)
    tdList.append(tdDigTabEnt)

    tdDigTabEnt = SimpleNamespace() # DigitalTable data
    tdDigTabEnt.index = -1
    tdDigTabEnt.flags = 0
    tdDigTabEnt.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.Array, po)
    tdDigTabEnt.nested.dimensions = [SimpleNamespace() for _ in range(2)]
    for dim in tdDigTabEnt.nested.dimensions:
        dim.flags = 0
        dim.fixedSize = -1
    tdDigTabEnt.nested.clients = [ SimpleNamespace() ]
    for client in tdDigTabEnt.nested.clients:
        cli_flags = 0
        client.index = -1
        client.flags = 0
        client.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.NumUInt8, po)
    tdList.append(tdDigTabEnt)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, blockref, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster


def newDigitalWaveformCluster(vi, blockref, idx, obj_flags, po):
    """ The DigitalWaveform is a Cluster with specific things inside
    """
    tdList = []
    tdEntry = SimpleNamespace() # t0
    tdEntry.index = -1
    tdEntry.flags = 0
    # Use block of 16 bytes as Timestamp
    tdEntry.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.Block, po)
    tdEntry.nested.blkSize = 16
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # dt
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.NumFloat64, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # Y
    tdEntry.index = -1
    tdEntry.flags = 0
    # The DigitalTable is a Cluster with specific things inside
    tdEntry.nested = newDigitalTableCluster(vi, blockref, -1, 0, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # error
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newErrorCluster(vi, blockref, -1, 0, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # attributes
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.LVVariant, po)
    tdList.append(tdEntry)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, blockref, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster


def newAnalogWaveformCluster(vi, blockref, idx, obj_flags, tdInner, po):
    """ The AnalogWaveform is a Cluster with specific things inside
    """
    tdList = []
    tdEntry = SimpleNamespace() # t0
    tdEntry.index = -1
    tdEntry.flags = 0
    # Use block of 16 bytes as Timestamp
    tdEntry.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.Block, po)
    tdEntry.nested.blkSize = 16
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # dt
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.NumFloat64, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # Y
    tdEntry.index = -1
    tdEntry.flags = 0
    # The AnalogTable is a Cluster with specific things inside
    tdEntry.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.Array, po)
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
    tdEntry.nested = newErrorCluster(vi, blockref, -1, 0, po)
    tdList.append(tdEntry)
    tdEntry = SimpleNamespace() # attributes
    tdEntry.index = -1
    tdEntry.flags = 0
    tdEntry.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.LVVariant, po)
    tdList.append(tdEntry)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, blockref, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster


def newDynamicTableCluster(vi, blockref, idx, obj_flags, po):
    """ The DynamicTable is a Cluster with specific things inside
    """
    # make list of fields
    tdList = []

    tdTabEnt = SimpleNamespace()
    tdTabEnt.index = -1
    tdTabEnt.flags = 0
    tdTabEnt.nested = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.Array, po)
    tdTabEnt.nested.dimensions = [SimpleNamespace() for _ in range(1)]
    for dim in tdTabEnt.nested.dimensions:
        dim.flags = 0
        dim.fixedSize = -1
    tdTabEnt.nested.clients = [ SimpleNamespace() ]
    for client in tdTabEnt.nested.clients:
        client.index = -1
        client.flags = 0
        # data inside as for MEASURE_DATA_FLAVOR.Float64Waveform
        tdInner = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.NumFloat64, po)
        client.nested = newAnalogWaveformCluster(vi, blockref, -1, 0, tdInner, po)
    tdList.append(tdTabEnt)

    # Prepare a cluster container for that list
    tdCluster = newTDObject(vi, blockref, idx, obj_flags, TD_FULL_TYPE.Cluster, po)
    tdCluster.clients = tdList
    return tdCluster

def newOldFloat64WaveformCluster(vi, blockref, idx, obj_flags, po):
    """ The OldFloat64 Waveform is a Cluster with specific things inside
    """
    #TODO this is not enough, some changes are required in the cluster
    tdInner = newTDObject(vi, blockref, -1, 0, TD_FULL_TYPE.NumFloat64, self.po)
    tdCluster = newAnalogWaveformCluster(vi, blockref, -1, 0, tdInner, self.po)
    return tdCluster


def parseTDSingleObject(vi, blockref, bldata, pos, clients, po):
    bldata.seek(pos)
    obj_type, obj_flags, obj_len = TDObject.parseRSRCDataHeader(bldata)
    obj_idx = -1
    if (po.verbose > 2):
        print("{:s}: TD sub-object at 0x{:04x}, type 0x{:02x} flags 0x{:02x} len {:d}"\
          .format(vi.src_fname, pos, obj_type, obj_flags, obj_len))
    if obj_len < 4:
        raise AttributeError("TD sub-object at 0x{:04x}, type 0x{:02x} flags 0x{:02x}, has length={:d} below minimum"\
          .format(pos, obj_type, obj_flags, obj_len))
        obj_type = TD_FULL_TYPE.Void
    obj = newTDObject(vi, blockref, obj_idx, obj_flags, obj_type, po)
    clientTD = SimpleNamespace()
    clientTD.index = -1 # Nested clients have index -1
    clientTD.flags = 0 # Only Type Mapped entries have it non-zero
    clientTD.nested = obj
    clients.append(clientTD)
    bldata.seek(pos)
    obj.setOwningList(clients)
    obj.initWithRSRC(bldata, obj_len)
    return obj.index, obj_len

def parseTDObject(vi, blockref, bldata, ver, po, useConsolidatedTypes=False):
    """ Reads TD object from RSRC file
    """
    clients = []
    hasTopType = 0
    topType = None
    if isSmallerVersion(ver, 8,0,0,1):
        raise NotImplementedError("Unsupported TD read in ver=0x{:06X} older than LV8.0".format(encodeVersion(ver)))
    elif useConsolidatedTypes and isGreaterOrEqVersion(ver, 8,6,0,1):
        # The TD is given by index instead of directly provided data
        topType = readVariableSizeFieldU2p2(bldata)
        hasTopType = 1
    else:
        # A list of TDs, with definitions directly in place; then index of top item is provided
        varcount = int.from_bytes(bldata.read(4), byteorder='big', signed=False)
        if varcount > po.typedesc_list_limit:
            raise AttributeError("TD sub-types count {:d} exceeds limit"\
              .format(varcount))
        pos = bldata.tell()
        for i in range(varcount):
            obj_idx, obj_len = parseTDSingleObject(vi, blockref, bldata, pos, clients, po)
            pos += obj_len
        bldata.seek(pos)
        hasTopType = readVariableSizeFieldU2p2(bldata)
        if hasTopType != 0:
            topType = readVariableSizeFieldU2p2(bldata)
    if hasTopType not in (0,1,):
        raise AttributeError("TypeDesc contains HasTopType with unsupported value 0x{:X}"\
          .format(hasTopType))
    return clients, topType

def prepareTDObject(vi, clients, topType, ver, po, useConsolidatedTypes=False, avoid_recompute=False):
    data_buf = b''
    if isSmallerVersion(ver, 8,0,0,1):
        raise NotImplementedError("Unsupported TypeDesc read in ver=0x{:06X} older than LV8.0".format(encodeVersion(ver)))
    elif useConsolidatedTypes and isGreaterOrEqVersion(ver, 8,6,0,1):
        data_buf += prepareVariableSizeFieldU2p2(topType)
    else:
        varcount = sum(1 for clientTD in clients if clientTD.index == -1)
        data_buf += int(varcount).to_bytes(4, byteorder='big', signed=False)
        for clientTD in clients:
            if clientTD.index != -1:
                continue
            clientTD.nested.updateData(avoid_recompute=avoid_recompute)
            data_buf += clientTD.nested.raw_data
        hasTopType = 0 if topType is None else 1
        data_buf += prepareVariableSizeFieldU2p2(hasTopType)
        if hasTopType != 0:
            data_buf += prepareVariableSizeFieldU2p2(topType)
    return data_buf

def initWithXMLTDObject(vi, blockref, obj_elem, po):
    clients = []
    topType = None
    topType_str = obj_elem.get("TopTypeID")
    if topType_str is not None and topType_str != "None":
        topType = int(topType_str, 0)
    for subelem in obj_elem:
        if (subelem.tag == "TypeDesc"):
            obj_idx = -1
            obj_type = valFromEnumOrIntString(TD_FULL_TYPE, subelem.get("Type"))
            obj_flags = importXMLBitfields(TYPEDESC_FLAGS, subelem)
            obj = newTDObject(vi, blockref, obj_idx, obj_flags, obj_type, po)
            clientTD = SimpleNamespace()
            clientTD.flags = 0
            clientTD.index = -1
            clientTD.nested = obj
            clients.append(clientTD)
            # Set TypeDesc data based on XML properties
            clientTD.nested.setOwningList(clients)
            clientTD.nested.initWithXML(subelem)
        else:
            pass
    return clients, topType

def initWithXMLTDObjectLate(vi, clients, topType, ver, po):
    for clientTD in clients:
        if clientTD.index == -1:
            clientTD.nested.initWithXMLLate()
    return

def exportXMLTDObject(vi, clients, topType, obj_elem, fname_base, po):
    hasTopType = 0 if topType is None else 1
    if hasTopType != 0:
        obj_elem.set("TopTypeID", "{:d}".format(topType))
    idx = -1
    for clientTD in clients:
        if clientTD.index != -1:
            continue
        idx += 1
        fname_cli = "{:s}_{:04d}".format(fname_base, idx)
        subelem = ET.SubElement(obj_elem,"TypeDesc")
        subelem.set("Type", stringFromValEnumOrInt(TD_FULL_TYPE, clientTD.nested.otype))

        clientTD.nested.exportXML(subelem, fname_cli)
        clientTD.nested.exportXMLFinish(subelem)
    return

def ctypeToFullTypeEnum(obj_ctype):
    """ Given a type from ctype module, returns TD_FULL_TYPE item
    """
    if obj_ctype in (c_bool,):
        return TD_FULL_TYPE.Boolean
    elif obj_ctype.__name__ in ("c_int8","c_byte","c_char",):
        return TD_FULL_TYPE.NumInt8
    elif obj_ctype.__name__ in ("c_int16","c_short","c_short_be",):
        return TD_FULL_TYPE.NumInt16
    elif obj_ctype.__name__ in ("c_int32","c_long","c_long_be",):
        return TD_FULL_TYPE.NumInt32
    elif obj_ctype.__name__ in ("c_int64","c_longlong","c_longlong_be",):
        return TD_FULL_TYPE.NumInt64
    elif obj_ctype.__name__ in ("c_uint8","c_ubyte","c_ubyte_be",):
        return TD_FULL_TYPE.NumUInt8
    elif obj_ctype.__name__ in ("c_uint16","c_ushort","c_ushort_be",):
        return TD_FULL_TYPE.NumUInt16
    elif obj_ctype.__name__ in ("c_uint32","c_ulong","c_ulong_be",):
        return TD_FULL_TYPE.NumUInt32
    elif obj_ctype.__name__ in ("c_uint64","c_ulonglong","c_ulonglong_be",):
        return TD_FULL_TYPE.NumUInt64
    elif obj_ctype.__name__ in ("c_float",):
        return TD_FULL_TYPE.NumFloat32
    elif obj_ctype.__name__ in ("c_double",):
        return TD_FULL_TYPE.NumFloat64
    elif obj_ctype.__name__ in ("c_longdouble",):
        return TD_FULL_TYPE.NumFloatExt
    return None

def numericToStringSimple(val, tdType):
    """ Converts numeric value to a string in a simple manner

    Values are sored with enough decimal places to cover precision of each type.
    The precision must be high enough to mind where the switch to scientific notation
    takes place.
    """
    text = None
    from LVdatatype import TD_FULL_TYPE
    if tdType in (TD_FULL_TYPE.NumInt8,TD_FULL_TYPE.NumInt16,TD_FULL_TYPE.NumInt32,TD_FULL_TYPE.NumInt64,):
        text = "{:d}".format(val)
    elif tdType in (TD_FULL_TYPE.NumUInt8,TD_FULL_TYPE.UnitUInt8,TD_FULL_TYPE.NumUInt16,TD_FULL_TYPE.UnitUInt16,\
      TD_FULL_TYPE.NumUInt32,TD_FULL_TYPE.UnitUInt32,TD_FULL_TYPE.NumUInt64,):
        text = "{:d}".format(val)
    elif tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
        text = "{:.9g}".format(val)
    elif tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
        text = "{:.17g}".format(val)
    elif tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
        text = "{:.39g}".format(val)
    return text

def numericToStringUnequivocal(val, tdType):
    """ Converts numeric value to a string in an unequivocal manner

    This is achieved by simply concatenating direct hex representation after a float. That is the only way
    to handle _all_ values, including different NaNs.
    Integers are simpler - the formatted value is unequivocal already.
    """
    text = None
    from LVdatatype import TD_FULL_TYPE
    if tdType in (TD_FULL_TYPE.NumInt8,TD_FULL_TYPE.NumInt16,TD_FULL_TYPE.NumInt32,TD_FULL_TYPE.NumInt64,):
        text = "{:d}".format(val)
    elif tdType in (TD_FULL_TYPE.NumUInt8,TD_FULL_TYPE.UnitUInt8,TD_FULL_TYPE.NumUInt16,TD_FULL_TYPE.UnitUInt16,\
      TD_FULL_TYPE.NumUInt32,TD_FULL_TYPE.UnitUInt32,TD_FULL_TYPE.NumUInt64,):
        text = "{:d}".format(val)
    elif tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
        # 32-bit float has 8 digit precision; adding one digit for the scientific notation margin
        tmpbt = struct.pack('>f', val)
        text = "{:.9g} (0x{:08X})".format(val, int.from_bytes(tmpbt, byteorder='big', signed=False))
    elif tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
        # 64-bit float has 17 digit precision
        tmpbt = struct.pack('>d', val)
        text = "{:.17g} (0x{:016X})".format(val, int.from_bytes(tmpbt, byteorder='big', signed=False))
    elif tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
        # Precision of 128-bit float is 36 digits, plus few for partial and for sci notation margin
        tmpbt = prepareQuadFloat(val)
        text = "{:.39g} (0x{:032X})".format(val, int.from_bytes(tmpbt, byteorder='big', signed=False))
    return text

def stringUnequivocalToNumeric(text, tdType):
    """ Converts a string (including unequivocal one) back to numeric value
    """
    val = None
    from LVdatatype import TD_FULL_TYPE
    if tdType in (TD_FULL_TYPE.NumInt8,TD_FULL_TYPE.NumInt16,TD_FULL_TYPE.NumInt32,TD_FULL_TYPE.NumInt64,):
        val = int(text.strip(),0)
    elif tdType in (TD_FULL_TYPE.NumUInt8,TD_FULL_TYPE.UnitUInt8,TD_FULL_TYPE.NumUInt16,TD_FULL_TYPE.UnitUInt16,\
      TD_FULL_TYPE.NumUInt32,TD_FULL_TYPE.UnitUInt32,TD_FULL_TYPE.NumUInt64,):
        val = int(text.strip(),0)
    elif tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,\
      TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
        if val is None: # Get the value from hex sting in brackets
            hexParse = re.search(r'^.*\((0x[0-9A-Fa-f]+)\)$',text.strip())
            if hexParse is None:
                pass
            elif tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
                tmpbt = int(hexParse.group(1),0).to_bytes(4, byteorder='big', signed=False)
                val = struct.unpack('>f', tmpbt)[0]
            elif tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
                tmpbt = int(hexParse.group(1),0).to_bytes(8, byteorder='big', signed=False)
                val = struct.unpack('>d', tmpbt)[0]
            elif tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
                tmpbt = int(hexParse.group(1),0).to_bytes(16, byteorder='big', signed=False)
                val = readQuadFloat(BytesIO(tmpbt))
        if val is None: # Get the value from formatted float
            hexParse = re.search(r'([\+-]?[0-9.]+([Ee][\+-]?[0-9]+)?|[\+-]?inf)',text)
            if hexParse is None:
                pass
            elif tdType in (TD_FULL_TYPE.NumFloat32,TD_FULL_TYPE.UnitFloat32,):
                val = float(hexParse.group(1))
            elif tdType in (TD_FULL_TYPE.NumFloat64,TD_FULL_TYPE.UnitFloat64,):
                val = float(hexParse.group(1))
            elif tdType in (TD_FULL_TYPE.NumFloatExt,TD_FULL_TYPE.UnitFloatExt,):
                from decimal import Decimal, localcontext
                with localcontext() as ctx:
                    # quad float has up to 36 digits precision, plus partial and sci notation switch margin
                    ctx.prec = 39 
                    val = Decimal(hexParse.group(1))
    return val

def newTDObject(vi, blockref, idx, obj_flags, obj_type, po):
    """ Creates and returns new Type Descriptor object with given parameters
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
    return ctor(vi, blockref, idx, obj_flags, obj_type, po)

