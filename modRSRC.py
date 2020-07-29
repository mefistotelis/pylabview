#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" LabView RSRC files modder.

Modifies XML version of RSRC files. Checks if XML is correct,
recovers missing or damaged parts.
"""

# Copyright (C) 2019-2020 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

__version__ = "0.0.1"
__author__ = "Mefistotelis"
__license__ = "MIT"

import sys
import re
import os
import argparse
import enum
from types import SimpleNamespace
from PIL import Image

import LVparts
from LVparts import PARTID, DSINIT
import LVxml as ET
from LVmisc import eprint

class FUNC_OPTS(enum.IntEnum):
    changed = 0

def representsInt(s):
    """ Checks if given string represents an integer.
    """
    try: 
        int(s)
        return True
    except ValueError:
        return False
    except TypeError:
        return False

def strToList(s):
    """ Parses given string representing a comma separated list in brackets.
    """
    try: 
        list_str = s.strip()
    except AttributeError:
        return None
    if list_str[0] != '(' or list_str[-1] != ')':
        return None
    list_str = list_str[1:-1].split(',')
    # We only need lists of integers
    for i in range(len(list_str)): 
        list_str[i] = int(list_str[i].strip(), 0)
    return list_str

def representsList(s):
    """ Checks if given string represents a comma separated list in brackets.
    """
    return strToList(s) is not None

def attribValToStr(val):
    if isinstance(val, str):
        strVal = val
    else:
        strVal = "{}".format(val)
    return strVal

def attribValFromStr(strVal, typeExample):
    if isinstance(typeExample, int):
        val = int(strVal, 0)
    else:
        val = strVal
    return val

def tagValToStr(val):
    if isinstance(val, str):
        strVal = val
    elif isinstance(val, (list, tuple)):
        strVal = '(' + ', '.join([str(x) for x in val]) + ')'
    else:
        strVal = "{}".format(val)
    return strVal

def boundsOverlap(rect1, rect2):
    """ Checks whether two rectangles overlap.

    Rectangles are defined as (x1,y1,x2,y2,).
    """
    if rect1[0] > rect2[2] or rect1[2] < rect2[0]:
        return False # Outside in vertical axis
    if rect1[1] > rect2[3] or rect1[3] < rect2[1]:
        return False # Outside in horizonal axis
    return True

def elemFindOrCreate(parentElem, elemName, fo, po, pos=-1):
    elem = parentElem.find(elemName)
    if elem is None:
        if pos == -1:
            elem = ET.SubElement(parentElem, elemName)
        else:
            elem = ET.Element(elemName)
            parentElem.insert(pos,elem)
        fo[FUNC_OPTS.changed] = True
    return elem

def attribGetOrSetDefault(elem, attrName, defVal, fo, po):
    """ Retrieves attribute value, setting default if not exist or wrong type.

    If the defVal type is integer, returned attibute is also converted to integer.
    """
    strVal = elem.get(attrName)
    if isinstance(defVal, int) and not representsInt(strVal):
        strVal = None
    if strVal is None:
        if defVal is not None:
            strVal = attribValToStr(defVal)
            elem.set(attrName, strVal)
        else:
            strVal = None
            elem.attrib.pop(attrName, None) # remove attrib, no exception if doesn't exist
        fo[FUNC_OPTS.changed] = True
    attrVal = attribValFromStr(strVal, defVal)
    return attrVal

def elemTextSetValue(elem, val, fo, po):
    """ Sets given value as content of the element.

    Returns string representation of the value set.
    """
    if val is not None:
        strVal = tagValToStr(val)
    else:
        strVal = None
    if elem.text != strVal:
        elem.text = strVal
        fo[FUNC_OPTS.changed] = True
    return strVal

def elemTextGetOrSetDefault(elem, defVal, fo, po):
    """ Retrieves value of element text, setting default if not exist or wrong type.

    If the defVal type is integer or list, returned attibute is also converted to that type.
    """
    attrVal = elem.text
    if isinstance(defVal, int):
         if not representsInt(attrVal):
            attrVal = None
    elif isinstance(defVal, (list, tuple)):
         if not representsList(attrVal):
            attrVal = None
    if attrVal is None:
        attrVal = elemTextSetValue(elem, defVal, fo, po)
    if isinstance(defVal, int):
        attrVal = int(attrVal, 0)
    return attrVal

def elemFindOrCreateWithAttribsAndTags(parentElem, elemName, attrs, tags, fo, po, parentPos=None):
    elem = None
    xpathAttrs = "".join([ "[@{}='{}']".format(attr[0],attribValToStr(attr[1])) for attr in attrs ] )
    if parentPos is not None:
        xpathAttrs += "["+str(parentPos)+"]"
    #elem_list = filter(lambda x: attrVal in x.get(attrName), parentElem.findall(".//{}[@{}='{}']".format(elemName,attrName)))
    elem_list = parentElem.findall(".//{}{}".format(elemName,xpathAttrs))
    for chk_elem in elem_list:
        matchFail = False
        for tag in tags:
            sub_elem = chk_elem.find(tag[0])
            if tag[1] is None:
                if sub_elem is not None and sub_elem.text is not None and sub_elem.text.strip() != '':
                    matchFail = True
            elif sub_elem is not None and sub_elem.text != tagValToStr(tag[1]):
                matchFail = True
            if matchFail:
                break
        if matchFail:
            continue
        elem = chk_elem
        break
    createdNew = False
    if elem is None:
        elem = ET.SubElement(parentElem, elemName)
        fo[FUNC_OPTS.changed] = True
        createdNew = True
    if (po.verbose > 1):
        print("{:s}: {} \"{}/{}\", attribs: {} sub-tags: {}".format(po.xml, "Creating new" if createdNew else "Reusing existing",parentElem.tag,elemName,attrs,tags))
    for attr in attrs:
        attrName = attr[0]
        attrVal = attr[1]
        attribGetOrSetDefault(elem, attrName, attrVal, fo, po)
    for tag in tags:
        if tag[1] is not None:
            sub_elem = elemFindOrCreate(elem, tag[0], fo, po)
            elemTextGetOrSetDefault(sub_elem, tag[1], fo, po)
        else:
            sub_elem = elem.find(tag[0])
            if sub_elem is not None:
                elem.remove(sub_elem)
    return elem

def getDFDSRecord(RSRC, typeID, po):
    """ Returns DFDS entry for given typeID.
    """
    DS_entry = RSRC.find("./DFDS/Section/DataFill[@TypeID='{}']".format(typeID))
    if DS_entry is None:
        return None
    return DS_entry

def getDSInitRecord(RSRC, po):
    """ Returns DSInit, which is a record of 51 integers of initialized data.

    Returns Element containing the values sub-tree.
    """
    DFDS = RSRC.find('./DFDS/Section')
    if DFDS is None:
        return None
    # Usually what we need will just be the first DFDS item. And even if not,
    # it's always first item with 51 ints inside. So instead of going though
    # type map and VCTP, we can localise the proper type directly.
    DSI_candidates = []
    DSI_candidates.extend( DFDS.findall('./DataFill/RepeatedBlock/I32/../..') )
    DSI_candidates.extend( DFDS.findall('./DataFill/Cluster/RepeatedBlock/I32/../../..') )
    for DSInit in DSI_candidates:
        NonCommentFields = list(filter(lambda f: f.tag is not ET.Comment, DSInit.findall(".//RepeatedBlock[1]/*")))
        # The element needs to have exactly 51 sub-elements, all Int32
        if len(NonCommentFields) == 51 and len(DSInit.findall('.//RepeatedBlock[1]/I32')) == 51:
            return DSInit
    # No matching type in DFDS
    return None

def getDSInitEntry(RSRC, entryId, po, DSInit=None):
    """ Returns DSInit entry value.
    """
    if DSInit is None:
        DSInit = getDSInitRecord(RSRC, po)
    if DSInit is None:
        return None
    entry_elem = DSInit.find("./RepeatedBlock[1]/I32["+str(int(entryId+1))+"]")
    if entry_elem is None:
        entry_elem = DSInit.find("./Cluster[1]/RepeatedBlock[1]/I32["+str(int(entryId+1))+"]")
    if entry_elem is None:
        return None
    return int(entry_elem.text,0)

def getFpDCOTable(RSRC, po, TM80_IndexShift=None, FpDCOTable_TypeID=None):
    """ Returns DCO Table from DataSpace.
    """
    if FpDCOTable_TypeID is None:
        if TM80_IndexShift is None:
            TM80 = RSRC.find("./TM80/Section")
            if TM80 is not None:
                TM80_IndexShift = TM80.get("IndexShift")
                if TM80_IndexShift is not None:
                    TM80_IndexShift = int(TM80_IndexShift, 0)
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.fpdcoTableTMI, po)
            if val_TMI is not None:
                FpDCOTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
    if FpDCOTable_TypeID is None:
        return None
    FpDCOTable = getDFDSRecord(RSRC, FpDCOTable_TypeID, po)
    return FpDCOTable

def getFpDCOTableAsList(RSRC, po, TM80_IndexShift=None, FpDCOTable_TypeID=None):
    """ Returns DCO Table from DataSpace, as list of Structs.
    """
    FpDCOTable = getFpDCOTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, FpDCOTable_TypeID=FpDCOTable_TypeID)
    FpDCOList = []
    if FpDCOTable is None:
        return FpDCOList
    for FpDCO in FpDCOTable.findall("./RepeatedBlock/Cluster"):
        DCO = dict()
        FpDCO_FieldList = list(filter(lambda f: f.tag is not ET.Comment, FpDCO.findall("./*")))
        for idx,field in enumerate(LVparts.DCO._fields_):
            fldName = field[0]
            fldType = field[1]
            fldVal = FpDCO_FieldList[idx].text
            if re.match(r"^c_u?int[0-9]+(_[lb]e)?$", fldType.__name__) or \
               re.match(r"^c_u?byte$", fldType.__name__) or \
               re.match(r"^c_u?short(_[lb]e)?$", fldType.__name__) or \
               re.match(r"^c_u?long(_[lb]e)?$", fldType.__name__):
                fldVal = int(fldVal,0)
            elif fldType in ("c_float","c_double","c_longdouble",):
                fldVal = float(fldVal)
            elif re.match(r"^c_u?byte_Array_[0-9]+$", fldType.__name__):
                fldVal = bytes.fromhex(fldVal)
            DCO[fldName] = fldVal
        FpDCOList.append(DCO)
    return FpDCOList

def getFpDCOEntry(RSRC, dcoIndex, po, TM80_IndexShift=None, FpDCOTable_TypeID=None):
    """ Returns DCO entry from DataSpace.
    """
    FpDCOTable = getFpDCOTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, FpDCOTable_TypeID=FpDCOTable_TypeID)
    if FpDCOTable is None:
        return None
    FpDCO = FpDCOTable.find("./RepeatedBlock/Cluster["+str(dcoIndex)+"]")
    return FpDCO

def getProbeTable(RSRC, po, TM80_IndexShift=None, ProbeTable_TypeID=None):
    """ Returns Probe Table from DataSpace.
    """
    if ProbeTable_TypeID is None:
        if TM80_IndexShift is None:
            TM80 = RSRC.find("./TM80/Section")
            if TM80 is not None:
                TM80_IndexShift = TM80.get("IndexShift")
                if TM80_IndexShift is not None:
                    TM80_IndexShift = int(TM80_IndexShift, 0)
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.probeTableTMI, po)
            if val_TMI is not None:
                ProbeTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
    if ProbeTable_TypeID is None:
        return None
    ProbeTable = getDFDSRecord(RSRC, ProbeTable_TypeID, po)
    return ProbeTable

def vers_Fix(RSRC, vers, ver, fo, po):
    sect_index = vers.get("Index")
    if sect_index is not None:
        sect_index = int(sect_index, 0)
    if sect_index not in (4,7,8,9,10,):
        sect_index = 4
        vers.set("Index","{}".format(sect_index))
        fo[FUNC_OPTS.changed] = True
    if vers.find("Version") is None:
        nver = ET.SubElement(vers, "Version")
        for attr_name in ("Major", "Minor", "Bugfix", "Stage", "Build", "Flags",):
            nver.set(attr_name, ver.get(attr_name))
        nver.set("Text", "")
        nver.set("Info", "{}.{}".format(ver.get("Major"), ver.get("Minor")))
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def elemCheckOrCreate_partList_arrayElement(parent, fo, po, aeClass="cosm", \
      aePartID=1, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, aeBounds=None, \
      aeImageResID=None, aeFgColor=None, aeBgColor=None, aeRefListLength=None, \
      aeHGrowNodeListLength=None):

    assert parent is not None

    searchTags = []
    searchTags.append( ("partID", int(aePartID),) )
    if aeMasterPart is not None:
        searchTags.append( ("masterPart", int(aeMasterPart),) )
    else:
        searchTags.append( ("masterPart", None,) )
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)
    attribGetOrSetDefault(arrayElement, "uid", 1, fo, po)

    if aeObjFlags is not None:
        objFlags = elemFindOrCreate(arrayElement, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(objFlags, aeObjFlags, fo, po)

    partID = elemFindOrCreate(arrayElement, "partID", fo, po)
    elemTextGetOrSetDefault(partID, int(aePartID), fo, po)

    if aeMasterPart is not None:
        masterPart = elemFindOrCreate(arrayElement, "masterPart", fo, po)
        elemTextGetOrSetDefault(masterPart, aeMasterPart, fo, po)

    if aeHowGrow is not None:
        howGrow = elemFindOrCreate(arrayElement, "howGrow", fo, po)
        elemTextGetOrSetDefault(howGrow, aeHowGrow, fo, po)

    if aeBounds is not None:
        bounds = elemFindOrCreate(arrayElement, "bounds", fo, po)
        elemTextGetOrSetDefault(bounds, aeBounds, fo, po)

    if aeImageResID is not None:
        image = elemFindOrCreate(arrayElement, "image", fo, po)
        attribGetOrSetDefault(image, "class", "Image", fo, po)
        ImageResID = elemFindOrCreate(image, "ImageResID", fo, po)
        elemTextGetOrSetDefault(ImageResID, aeImageResID, fo, po)

    if aeFgColor is not None:
        fgColor = elemFindOrCreate(arrayElement, "fgColor", fo, po)
        elemTextGetOrSetDefault(fgColor, "{:08X}".format(aeFgColor), fo, po)

    if aeBgColor is not None:
        bgColor = elemFindOrCreate(arrayElement, "bgColor", fo, po)
        elemTextGetOrSetDefault(bgColor, "{:08X}".format(aeBgColor), fo, po)

    if aeRefListLength is not None:
        refListLength = elemFindOrCreate(arrayElement, "refListLength", fo, po)
        elemTextGetOrSetDefault(refListLength, aeRefListLength, fo, po)

    if aeHGrowNodeListLength is not None:
        hGrowNodeListLength = elemFindOrCreate(arrayElement, "hGrowNodeListLength", fo, po)
        elemTextGetOrSetDefault(hGrowNodeListLength, aeHGrowNodeListLength, fo, po)

    return arrayElement

def elemCheckOrCreate_table_arrayElement(parent, fo, po, aeClass="SubCosm", \
      aeObjFlags=None, aeBounds=None, \
      aeImageResID=None, aeFgColor=None, aeBgColor=None, parentPos=None):

    searchTags = []
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po, parentPos=parentPos)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)

    if aeObjFlags is not None:
        objFlags = elemFindOrCreate(arrayElement, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(objFlags, aeObjFlags, fo, po)

    if aeBounds is not None:
        bounds = elemFindOrCreate(arrayElement, "Bounds", fo, po)
        elemTextGetOrSetDefault(bounds, aeBounds, fo, po)

    if aeFgColor is not None:
        fgColor = elemFindOrCreate(arrayElement, "FGColor", fo, po)
        elemTextGetOrSetDefault(fgColor, "{:08X}".format(aeFgColor), fo, po)

    if aeBgColor is not None:
        bgColor = elemFindOrCreate(arrayElement, "BGColor", fo, po)
        elemTextGetOrSetDefault(bgColor, "{:08X}".format(aeBgColor), fo, po)

    if aeImageResID is not None:
        image = elemFindOrCreate(arrayElement, "Image", fo, po)
        attribGetOrSetDefault(image, "class", "Image", fo, po)
        ImageResID = elemFindOrCreate(image, "ImageResID", fo, po)
        elemTextGetOrSetDefault(ImageResID, aeImageResID, fo, po)

    return arrayElement

def elemCheckOrCreate_table_arrayElementImg(parent, fo, po, aeClass="Image", \
      aeImageResID=None, parentPos=None):

    searchTags = []
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po, parentPos=parentPos)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)

    if aeImageResID is not None:
        ImageResID = elemFindOrCreate(arrayElement, "ImageResID", fo, po)
        elemTextGetOrSetDefault(ImageResID, aeImageResID, fo, po)

    return arrayElement

def getConsolidatedTopTypeAndID(RSRC, typeID, po, VCTP=None):
    if VCTP is None:
        VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None:
        return None, None
    VCTP_TopTypeDesc = VCTP.find("./TopLevel/TypeDesc[@Index='{}']".format(typeID))
    if VCTP_TopTypeDesc is None:
        return None, None
    VCTP_FlatTypeID = VCTP_TopTypeDesc.get("FlatTypeID")
    if VCTP_FlatTypeID is None:
        return None, None
    VCTP_FlatTypeID = int(VCTP_FlatTypeID, 0)
    VCTP_FlatTypeDesc = VCTP.find("./TypeDesc["+str(VCTP_FlatTypeID+1)+"]")
    return VCTP_FlatTypeDesc, VCTP_FlatTypeID

def getConsolidatedTopType(RSRC, typeID, po, VCTP=None):
    VCTP_FlatTypeDesc, _ = getConsolidatedTopTypeAndID(RSRC, typeID, po, VCTP=VCTP)
    return VCTP_FlatTypeDesc

def getConsolidatedFlatType(RSRC, flatTypeID, po):
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None:
        return None
    VCTP_FlatTypeDesc = VCTP.find("./TypeDesc["+str(flatTypeID+1)+"]")
    return VCTP_FlatTypeDesc

def valueOfTypeToXML(valueType, val, po):
    """ Returns dict of values for its XML representation of given type

    Returns dict with tag:value pairs, text property of the base element is under "tagText" key.
    """
    if valueType in ("Boolean", "BooleanU16",):
        valDict = { "tagText" : str(val) }
    elif valueType in ("NumInt8", "NumInt16", "NumInt32", "NumInt64",):
        valDict = { "tagText" : str(val) }
    elif valueType in ("NumUInt8", "NumUInt16", "NumUInt32", "NumUInt64",\
      "UnitUInt8", "UnitUInt16", "UnitUInt32",):
        valDict = { "tagText" : str(val) }
    elif valueType in ("NumFloat32", "NumFloat64", "NumFloatExt",\
      "UnitFloat32", "UnitFloat64", "UnitFloatExt",):
        valDict = { "tagText" : str(val) }
    elif valueType in ("NumComplex64", "NumComplex128", "NumComplexExt",\
      "UnitComplex64", "UnitComplex128", "UnitComplexExt",):
        valDict = { "real" : str(val[0]), "imaginary" : str(val[1]) }
    else:
        valDict = { "tagText" : str(val) }
    return valDict

def valueTypeGetDefaultRange(valueType, po):
    if valueType in ("Boolean", "BooleanU16",):
        stdMin = 0
        stdMax = 1
        stdInc = 1
    elif valueType == "NumInt8":
        stdMin = -128
        stdMax = 127
        stdInc = 1
    elif valueType == "NumInt16":
        stdMin = -32768
        stdMax = 32767
        stdInc = 1
    elif valueType == "NumInt32":
        stdMin = -2147483648
        stdMax = 2147483647
        stdInc = 1
    elif valueType == "NumInt64":
        stdMin = -9223372036854775808
        stdMax = 9223372036854775807
        stdInc = 1
    elif valueType == "NumUInt8":
        stdMin = 0
        stdMax = 255
        stdInc = 1
    elif valueType == "NumUInt16":
        stdMin = 0
        stdMax = 65535
        stdInc = 1
    elif valueType == "NumUInt32":
        stdMin = 0
        stdMax = 4294967295
        stdInc = 1
    elif valueType == "NumUInt64":
        stdMin = 0
        stdMax = 18446744073709551615
        stdInc = 1
    elif valueType == "NumFloat32":
        stdMin = -3.402823466E+38
        stdMax = 3.402823466E+38
        stdInc = 0.1
    elif valueType == "NumFloat64":
        stdMin = -1.7976931348623158E+308
        stdMax = 1.7976931348623158E+308
        stdInc = 0.1
    elif valueType == "NumFloatExt":
        stdMin = None
        stdMax = None
        stdInc = 0.1
    elif valueType == "NumComplex64":
        stdMin = (-3.402823466E+38, -3.402823466E+38,)
        stdMax = (3.402823466E+38, 3.402823466E+38,)
        stdInc = (0.1, 0.1,)
    elif valueType == "NumComplex128":
        stdMin = (-1.7976931348623158E+308, -1.7976931348623158E+308)
        stdMax = (1.7976931348623158E+308, 1.7976931348623158E+308)
        stdInc = (0.1, 0.1,)
    elif valueType == "NumComplexExt":
        stdMin = None
        stdMax = None
        stdInc = (0.1, 0.1,)
    #elif valueType == "UnitUInt8":
    #elif valueType == "UnitUInt16":
    #elif valueType == "UnitUInt32":
    #elif valueType == "UnitFloat32":
    #elif valueType == "UnitFloat64":
    #elif valueType == "UnitFloatExt":
    #elif valueType == "UnitComplex64":
    #elif valueType == "UnitComplex128":
    #elif valueType == "UnitComplexExt":
    else:
        stdMin = None
        stdMax = None
        stdInc = None
    return stdMin, stdMax, stdInc


def elemCheckOrCreate_paneHierarchy_content(paneHierarchy, fo, po, aeObjFlags=None, \
          aeHowGrow=None, aeBounds=None, hasParts=False, aePaneFlags=None, aeMinPaneSize=None, \
          aeOrigin=None, aeDocBounds=None, hasZPlane=True, aeImageResID=None):
    """ Fils content of pre-created paneHierarchy tag
    """
    if aeObjFlags is not None:
        ph_objFlags = elemFindOrCreate(paneHierarchy, "objFlags", fo, po)
        objFlags_val = elemTextGetOrSetDefault(ph_objFlags, aeObjFlags, fo, po)

    if aeHowGrow is not None:
        ph_howGrow = elemFindOrCreate(paneHierarchy, "howGrow", fo, po)
        elemTextGetOrSetDefault(ph_howGrow, aeHowGrow, fo, po)

    if aeBounds is not None:
        ph_bounds = elemFindOrCreate(paneHierarchy, "bounds", fo, po)
        elemTextGetOrSetDefault(ph_bounds, aeBounds, fo, po)

    if hasParts:
        ph_partsList = elemFindOrCreate(paneHierarchy, "partsList", fo, po)
        attribGetOrSetDefault(ph_partsList, "elements", 0, fo, po)

    if aePaneFlags is not None:
        ph_paneFlags = elemFindOrCreate(paneHierarchy, "paneFlags", fo, po)
        elemTextGetOrSetDefault(ph_paneFlags, aePaneFlags, fo, po)

    if aeMinPaneSize is not None:
        ph_minPaneSize = elemFindOrCreate(paneHierarchy, "minPaneSize", fo, po)
        elemTextGetOrSetDefault(ph_minPaneSize, aeMinPaneSize, fo, po)

    if aeOrigin is not None:
        ph_origin = elemFindOrCreate(paneHierarchy, "origin", fo, po)
        elemTextGetOrSetDefault(ph_origin, aeOrigin, fo, po)

    if aeDocBounds is not None:
        ph_docBounds = elemFindOrCreate(paneHierarchy, "docBounds", fo, po)
        elemTextGetOrSetDefault(ph_docBounds, aeDocBounds, fo, po)

    ph_zPlaneList = None
    if hasZPlane:
        ph_zPlaneList = elemFindOrCreate(paneHierarchy, "zPlaneList", fo, po)
        attribGetOrSetDefault(ph_zPlaneList, "elements", 0, fo, po)

    if aeImageResID is not None:
        ph_image = elemFindOrCreate(paneHierarchy, "image", fo, po)
        attribGetOrSetDefault(ph_image, "class", "Image", fo, po)

        ph_image_ImageResID = elemFindOrCreate(ph_image, "ImageResID", fo, po)
        elemTextGetOrSetDefault(ph_image_ImageResID, aeImageResID, fo, po)

    return ph_zPlaneList, ph_partsList, objFlags_val

def elemCheckOrCreate_ddo_content(ddo, fo, po, aeDdoObjFlags=None, aeBounds=None, \
          hasParts=False, aeDdoTypeID=None, aeMouseWheelSupport=None, aeMinButSize=None, \
          valueType="Boolean", aeStdNumMin=None, aeStdNumMax=None, aeStdNumInc=None, \
          aeSavedSize=None):
    """ Fils content of pre-created DDO tag
    """

    if aeDdoObjFlags is not None:
        ddo_objFlags = elemFindOrCreate(ddo, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(ddo_objFlags, aeDdoObjFlags, fo, po)

    if aeBounds is not None:
        ddo_bounds = elemFindOrCreate(ddo, "bounds", fo, po)
        elemTextGetOrSetDefault(ddo_bounds, aeBounds, fo, po)

    partsList = None
    if hasParts:
        partsList = elemFindOrCreate(ddo, "partsList", fo, po)
        attribGetOrSetDefault(partsList, "elements", 0, fo, po)

    if aeDdoTypeID is not None:
        ddo_TypeDesc = elemFindOrCreate(ddo, "typeDesc", fo, po)
        elemTextGetOrSetDefault(ddo_TypeDesc, "TypeID({})".format(aeDdoTypeID), fo, po)

    if aeMouseWheelSupport is not None:
        ddo_MouseWheelSupport = elemFindOrCreate(ddo, "MouseWheelSupport", fo, po)
        elemTextGetOrSetDefault(ddo_MouseWheelSupport, aeMouseWheelSupport, fo, po)

    if aeMinButSize is not None:
        ddo_MinButSize = elemFindOrCreate(ddo, "MinButSize", fo, po)
        elemTextGetOrSetDefault(ddo_MinButSize, aeMinButSize, fo, po)

    if aeStdNumMin is not None:
        ddo_StdNumMin = elemFindOrCreate(ddo, "StdNumMin", fo, po)
        aeStdNumMin_dict = valueOfTypeToXML(valueType, aeStdNumMin, po)
        for tagName, tagValue in aeStdNumMin_dict.items():
            if tagName == "tagText":
                elemTextGetOrSetDefault(ddo_StdNumMin, tagValue, fo, po)
                continue
            tmp_subtag = elemFindOrCreate(ddo_StdNumMin, tagName, fo, po)
            elemTextGetOrSetDefault(tmp_subtag, tagValue, fo, po)

    if aeStdNumMax is not None:
        ddo_StdNumMax = elemFindOrCreate(ddo, "StdNumMax", fo, po)
        aeStdNumMax_dict = valueOfTypeToXML(valueType, aeStdNumMax, po)
        for tagName, tagValue in aeStdNumMax_dict.items():
            if tagName == "tagText":
                elemTextGetOrSetDefault(ddo_StdNumMax, tagValue, fo, po)
                continue
            tmp_subtag = elemFindOrCreate(ddo_StdNumMax, tagName, fo, po)
            elemTextGetOrSetDefault(tmp_subtag, tagValue, fo, po)

    if aeStdNumInc is not None:
        ddo_StdNumInc = elemFindOrCreate(ddo, "StdNumInc", fo, po)
        aeStdNumInc_dict = valueOfTypeToXML(valueType, aeStdNumInc, po)
        for tagName, tagValue in aeStdNumInc_dict.items():
            if tagName == "tagText":
                elemTextGetOrSetDefault(ddo_StdNumInc, tagValue, fo, po)
                continue
            tmp_subtag = elemFindOrCreate(ddo_StdNumInc, tagName, fo, po)
            elemTextGetOrSetDefault(tmp_subtag, tagValue, fo, po)

    paneHierarchy = None
    if valueType == "Cluster": # Some types have sub-lists of objects
        ddo_ddoList = elemFindOrCreate(ddo, "ddoList", fo, po)
        attribGetOrSetDefault(ddo_ddoList, "elements", 0, fo, po)

        paneHierarchy = elemFindOrCreate(ddo, "paneHierarchy", fo, po)
        attribGetOrSetDefault(paneHierarchy, "class", "pane", fo, po)
        attribGetOrSetDefault(paneHierarchy, "uid", 1, fo, po)

    if aeSavedSize is not None:
        ddo_savedSize = elemFindOrCreate(ddo, "savedSize", fo, po)
        elemTextGetOrSetDefault(ddo_savedSize, aeSavedSize, fo, po)

    return partsList, paneHierarchy

def elemCheckOrCreate_zPlaneList_arrayElement_DDO(parent, fo, po, aeClass="fPDCO", \
          aeTypeID=1, aeObjFlags=None, aeDdoClass="stdNum", aeConNum=None, \
          aeTermListLength=None):
    """ Creates ArrayElement for top level controls
    """
    searchTags = []
    searchTags.append( ("typeDesc", "TypeID({})".format(aeTypeID),) )
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeClass,), ), searchTags, fo, po)
    attribGetOrSetDefault(arrayElement, "class", aeClass, fo, po)
    attribGetOrSetDefault(arrayElement, "uid", 1, fo, po)

    if aeObjFlags is not None:
        objFlags = elemFindOrCreate(arrayElement, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(objFlags, aeObjFlags, fo, po)

    if aeTypeID is not None:
        typeDesc = elemFindOrCreate(arrayElement, "typeDesc", fo, po)
        elemTextGetOrSetDefault(typeDesc, "TypeID({})".format(aeTypeID), fo, po)

    ddo = elemFindOrCreate(arrayElement, "ddo", fo, po)
    attribGetOrSetDefault(ddo, "class", aeDdoClass, fo, po)
    attribGetOrSetDefault(ddo, "uid", 1, fo, po)

    # Not having a "conNum" set seem to actually mean it's equal to 0, which
    # means it is set. The value with the meaning of 'unset' is -1.
    if aeConNum is not None:
        conNum = elemFindOrCreate(arrayElement, "conNum", fo, po)
        elemTextGetOrSetDefault(conNum, aeConNum, fo, po)

    if aeTermListLength is not None:
        termListLength = elemFindOrCreate(arrayElement, "termListLength", fo, po)
        elemTextGetOrSetDefault(termListLength, aeTermListLength, fo, po)

    # Now content of 'arrayElement/ddo'
    return arrayElement, ddo

def elemCheckOrCreate_zPlaneList_arrayElement(parent, fo, po, aeClass="fPDCO", \
          aeTypeID=1, aeObjFlags=None, aeDdoClass="stdNum", aeConNum=None, \
          aeTermListLength=None):
    """ Creates ArrayElement for nested controls, which are not stand-alone DCOs
    """
    searchTags = []
    searchTags.append( ("typeDesc", "TypeID({})".format(aeTypeID),) )
    arrayElement = elemFindOrCreateWithAttribsAndTags(parent, "SL__arrayElement", \
      ( ("class", aeDdoClass,), ), searchTags, fo, po)
    attribGetOrSetDefault(arrayElement, "class", aeDdoClass, fo, po)
    attribGetOrSetDefault(arrayElement, "uid", 1, fo, po)

    return arrayElement, arrayElement

def getConnectorPortsCount(RSRC, ver, fo, po):
    """ Returns amount of connector ports the RSRC uses.
    """
    # Get the value from connectors TypeDesc
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is not None:
        TypeDesc = None
        CONP_TypeDesc = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDesc is not None:
            CONP_TypeID = CONP_TypeDesc.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
            if CONP_TypeID is not None:
                TypeDesc = getConsolidatedTopType(RSRC, CONP_TypeID, po)
            if TypeDesc.get("Type") != "Function":
                # In .ctl files, this can reference TypeDef instead of Function
                eprint("{:s}: CONP references incorrect TD entry".format(po.xml))
                TypeDesc = None
        #TODO We could also detect the type with connectors by finding "Function" TDs, without CONP
        if TypeDesc is not None:
            count = len(TypeDesc.findall("./TypeDesc"))
        if count is not None:
            if count >= 1 and count <= 28:
                if (po.verbose > 1):
                    print("{:s}: Getting connector ports count for \"conPane/cons\" from VCTP Function entries".format(po.xml))
            else:
                    count = None
    # If failed, get the value from DSInit
    if count is None:
        count = getDSInitEntry(RSRC, DSINIT.nConnections, po)
        if count is not None:
            if count >= 1 and count <= 28:
                if (po.verbose > 1):
                    print("{:s}: Getting connector ports count for \"conPane/cons\" from DSInit Record".format(po.xml))
            else:
                    count = None
    return count

def getConnectorPortsFixedCount(RSRC, ver, fo, po):
    """ Returns amount of connector ports the RSRC uses.

    If the value is invalid, fixes it.
    """
    count = getConnectorPortsCount(RSRC, ver, fo, po)
    if count is not None:
        # Terminal patterns nly allow specific amounts of connectors
        if count > 12 and count < 16: count = 16
        if count > 16 and count < 20: count = 20
        if count > 20 and count < 28: count = 28
        if count >= 1 and count <= 28:
            return count
    return 12 # A default value if no real one found (4815 is the most popular pattern)

def recountHeapElements(RSRC, Heap, ver, fo, po):
    """ Updates 'elements' attributes in the Heap tree
    """
    elems = Heap.findall(".//*[@elements]")
    # The 'cons' tag does not store amount of elements inside, or rather - trivial entries are skipped
    cons_elem = Heap.find(".//conPane/cons")
    if cons_elem is not None:
        count = None
        if cons_elem in elems: elems.remove(cons_elem)
        count = getConnectorPortsFixedCount(RSRC, ver, fo, po)
        count_str = str(count)
        if (cons_elem.get("elements") != count_str):
            cons_elem.set("elements", count_str)
    # For the rest = count the elements
    for elem in elems:
        count = len(elem.findall("SL__arrayElement"))
        count_str = str(count)
        if elem.get("elements") != count_str:
            elem.set("elements", count_str)
            fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def checkOrCreateParts_RootPane(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of the 'root/paneHierarchy/partsList' element
    """
    # NAME_LABEL properties taken from empty VI file created in LV14
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1511754, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=5,
      aeBounds=[0,0,15,27], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 1028, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    # Y_SCROLLBAR properties taken from empty VI file created in LV14
    objFlags = 0x0d72
    if (parentObjFlags & 0x0008) == 0x0008: # if vert scrollbar marked as disabled
        objFlags |= 0x1008
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.Y_SCROLLBAR, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=194, \
      aeBounds=[0,1077,619,1093], aeImageResID=0, aeBgColor=0x00B3B3B3)

    # X_SCROLLBAR properties taken from empty VI file created in LV14
    objFlags = 0x1d73
    if (parentObjFlags & 0x0004) == 0x0004: # if horiz scrollbar marked as disabled
        objFlags |= 0x1008
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.X_SCROLLBAR, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=56, \
      aeBounds=[619,0,635,1077], aeImageResID=0, aeBgColor=0x00B3B3B3)

    # EXTRA_FRAME_PART properties taken from empty VI file created in LV14
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.EXTRA_FRAME_PART, aeObjFlags=7543, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=10,
      aeBounds=[619,1077,635,1093], aeImageResID=-365, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3)

    # CONTENT_AREA properties taken from empty VI file created in LV14
    contentArea = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.CONTENT_AREA, aeObjFlags=4211, aeMasterPart=None, aeHowGrow=120, \
      aeBounds=[0,0,619,1077], aeImageResID=-704, aeFgColor=0x00E2E2E2, aeBgColor=0x00E2E2E2)

    # ANNEX properties taken from empty VI file created in LV14
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)

    return contentArea

def checkOrCreateParts_ClusterPane(RSRC, partsList, parentObjFlags, labelText, corSz, fo, po):
    """ Checks content of the 'ddo/paneHierarchy/partsList' element for Cluster DCO
    """
    # NAME_LABEL properties taken from empty VI file created in LV14
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1511754, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=4096,
      aeBounds=[0,0,15,27], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 1028, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    # Y_SCROLLBAR properties taken from empty VI file created in LV14
    objFlags = 0x0d72
    if True: # if vert scrollbar marked as disabled
        objFlags |= 0x1000 | 0x0008 | 0x0004
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.Y_SCROLLBAR, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=194, \
      aeBounds=[0,corSz[1]-8,corSz[0]-25,corSz[1]+8], aeImageResID=0, aeBgColor=0x00B3B3B3)

    # X_SCROLLBAR properties taken from empty VI file created in LV14
    objFlags = 0x1d72
    if True: # if horiz scrollbar marked as disabled
        objFlags |= 0x1000 | 0x0008 | 0x0004
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.X_SCROLLBAR, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=56, \
      aeBounds=[corSz[0]-25,0,corSz[0]-9,corSz[1]-8], aeImageResID=0, aeBgColor=0x00B3B3B3)

    objFlags = 0x1d73
    if True: # if horiz scrollbar marked as disabled
        objFlags |= 0x1000 | 0x0008 | 0x0004
    # EXTRA_FRAME_PART properties taken from empty VI file created in LV14
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.EXTRA_FRAME_PART, aeObjFlags=objFlags, aeMasterPart=PARTID.CONTENT_AREA, aeHowGrow=4096,
      aeBounds=[corSz[0]-25,corSz[1]-8,corSz[0]-9,corSz[1]+8], aeImageResID=-365, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3)

    # CONTENT_AREA properties taken from empty VI file created in LV14
    contentArea = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.CONTENT_AREA, aeObjFlags=4211, aeMasterPart=None, aeHowGrow=120, \
      aeBounds=[0,0,corSz[0]-25,corSz[1]-8], aeImageResID=-704, aeFgColor=0x00969696, aeBgColor=0x00B3B3B3)

    # ANNEX properties taken from empty VI file created in LV14
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX, aeRefListLength=0, aeHGrowNodeListLength=0)

    return contentArea

def checkOrCreateParts_MultiCosm(RSRC, partsList, parentObjFlags, fo, po):
    """ Checks content of partsList sub-element of bigMultiCosm type
    """
    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="SubCosm", \
      aePartID=None, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="SubCosm", \
      aePartID=None, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="SubCosm", \
      aePartID=None, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="SubCosm", \
      aePartID=None, aeObjFlags=None, aeMasterPart=None, aeHowGrow=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)


def checkOrCreateParts_stdBool_control(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Boolean Control type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507655, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=4096,
      aeBounds=[0,5,15,46], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    boolLight = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_LIGHT, aeObjFlags=2354, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
      aeBounds=[27,35,38,50], aeImageResID=None, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)
    boolLight_table = elemFindOrCreate(boolLight, "table", fo, po)
    attribGetOrSetDefault(boolLight_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolLight_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,11,15], aeImageResID=-406, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolLight_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,11,15], aeImageResID=-406, aeFgColor=0x0064FF00, aeBgColor=0x0064FF00, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolLight_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,11,15], aeImageResID=-406, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolLight_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,11,15], aeImageResID=-406, aeFgColor=0x0064FF00, aeBgColor=0x0064FF00, parentPos=4)

    boolButton = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_BUTTON, aeObjFlags=2326, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[22,5,43,55], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    boolButton_table = elemFindOrCreate(boolButton, "table", fo, po)
    attribGetOrSetDefault(boolButton_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,50], aeImageResID=-407, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,50], aeImageResID=-407, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,50], aeImageResID=-407, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,50], aeImageResID=-407, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=4)

    aeObjFlags = 0x1937
    if (parentObjFlags & 0x01) != 0:
        aeObjFlags &= ~0x1000
    boolGlyph = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_SHADOW, aeObjFlags=aeObjFlags, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
      aeBounds=[22,5,48,60], aeImageResID=None, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3)
    boolGlyph_table = elemFindOrCreate(boolGlyph, "table", fo, po)
    attribGetOrSetDefault(boolGlyph_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,26,55], aeImageResID=-444, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,26,55], aeImageResID=0, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,26,55], aeImageResID=-444, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,26,55], aeImageResID=0, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=4)

    boolDivot = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_DIVOT, aeObjFlags=2359, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
      aeBounds=[17,0,48,60], aeImageResID=None, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3)
    boolDivot_table = elemFindOrCreate(boolDivot, "table", fo, po)
    attribGetOrSetDefault(boolDivot_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolDivot_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,31,60], aeImageResID=-408, aeFgColor=0x00B3B3B3, aeBgColor=0x00B3B3B3, parentPos=1)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21001, fo, po)

    return boolButton

def checkOrCreateParts_stdBool_indicator(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Boolean Indicator type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507655, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=4096,
      aeBounds=[0,0,15,50], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    boolButton = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_BUTTON, aeObjFlags=2324, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[19,2,36,19], aeImageResID=None, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00)
    boolButton_table = elemFindOrCreate(boolButton, "table", fo, po)
    attribGetOrSetDefault(boolButton_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x0064FF00, aeBgColor=0x0064FF00, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x001E4B00, aeBgColor=0x001E4B00, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolButton_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,17,17], aeImageResID=-404, aeFgColor=0x0064FF00, aeBgColor=0x0064FF00, parentPos=4)

    aeObjFlags = 0x1937
    if (parentObjFlags & 0x01) != 0 or True: # This whole function is for indicators
        aeObjFlags &= ~0x1000
    boolGlyph = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.BOOLEAN_GLYPH, aeObjFlags=aeObjFlags, aeMasterPart=PARTID.BOOLEAN_BUTTON, aeHowGrow=3840, \
      aeBounds=[17,0,38,21], aeImageResID=None, aeFgColor=0x00B3B3B3, aeBgColor=0x00006600)
    boolGlyph_table = elemFindOrCreate(boolGlyph, "table", fo, po)
    attribGetOrSetDefault(boolGlyph_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,21], aeImageResID=-411, aeFgColor=0x00B3B3B3, aeBgColor=0x00006600, parentPos=1)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,21], aeImageResID=-411, aeFgColor=0x00B3B3B3, aeBgColor=0x0000FF00, parentPos=2)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,21], aeImageResID=-411, aeFgColor=0x00B3B3B3, aeBgColor=0x00009900, parentPos=3)
    elemCheckOrCreate_table_arrayElement(boolGlyph_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,21,21], aeImageResID=-411, aeFgColor=0x00B3B3B3, aeBgColor=0x00009900, parentPos=4)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21012, fo, po)

    return boolButton

def checkOrCreateParts_stdNum_control(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Numeric Control type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,11,15,52], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    numText = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="numLabel", \
      aePartID=PARTID.NUMERIC_TEXT, aeObjFlags=264498, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[19,15,34,61], aeImageResID=-239, aeFgColor=0x00FAFAFA, aeBgColor=0x00FAFAFA)
    numText_textRec = elemFindOrCreate(numText, "textRec", fo, po)
    attribGetOrSetDefault(numText_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText_textRec, "mode", fo, po), 8389634, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText_textRec, "bgColor", fo, po), "{:08X}".format(0x00FAFAFA), fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText, "format", fo, po), "\"%#_g\"", fo, po)

    numIncr = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.INCREMENT, aeObjFlags=2358, aeMasterPart=PARTID.FRAME, aeHowGrow=12288, \
      aeBounds=[14,0,26,12], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    numIncr_table = elemFindOrCreate(numIncr, "table", fo, po)
    attribGetOrSetDefault(numIncr_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(numIncr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-413, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(numIncr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-413, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)

    numDecr = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.DECREMENT, aeObjFlags=2354, aeMasterPart=PARTID.FRAME, aeHowGrow=12288, \
      aeBounds=[26,0,38,12], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    numDecr_table = elemFindOrCreate(numDecr, "table", fo, po)
    attribGetOrSetDefault(numDecr_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(numDecr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-414, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(numDecr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-414, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)

    numRadix = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4288, \
      aeBounds=[19,15,34,21], aeImageResID=None, aeFgColor=0x00D9DADC, aeBgColor=0x007586A0)
    numRadix_table = elemFindOrCreate(numRadix, "table", fo, po)
    attribGetOrSetDefault(numRadix_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2000, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2001, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2002, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2003, parentPos=4)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2095, parentPos=5)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[15,11,38,65], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21003, fo, po)

    return numText

def checkOrCreateParts_stdNum_indicator(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of Numeric Indicator type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,50], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    numText = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="numLabel", \
      aePartID=PARTID.NUMERIC_TEXT, aeObjFlags=264498, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[19,4,34,50], aeImageResID=-239, aeFgColor=0x00D2D2D2, aeBgColor=0x00D2D2D2)
    numText_textRec = elemFindOrCreate(numText, "textRec", fo, po)
    attribGetOrSetDefault(numText_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText_textRec, "mode", fo, po), 8389634, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText_textRec, "bgColor", fo, po), "{:08X}".format(0x00D2D2D2), fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(numText, "format", fo, po), "\"%#_g\"", fo, po)

    numIncr = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.INCREMENT, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=12288, \
      aeBounds=[14,-11,26,1], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    numIncr_table = elemFindOrCreate(numIncr, "table", fo, po)
    attribGetOrSetDefault(numIncr_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(numIncr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-413, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(numIncr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-413, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)

    numDecr = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="bigMultiCosm", \
      aePartID=PARTID.DECREMENT, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=12288, \
      aeBounds=[26,-11,38,1], aeImageResID=None, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC)
    numDecr_table = elemFindOrCreate(numDecr, "table", fo, po)
    attribGetOrSetDefault(numDecr_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElement(numDecr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-414, aeFgColor=0x00BCBCBC, aeBgColor=0x00BCBCBC, parentPos=1)
    elemCheckOrCreate_table_arrayElement(numDecr_table, fo, po, aeClass="SubCosm", aeObjFlags=None, \
      aeBounds=[0,0,12,12], aeImageResID=-414, aeFgColor=0x00969696, aeBgColor=0x00969696, parentPos=2)

    numRadix = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4288, \
      aeBounds=[19,4,34,10], aeImageResID=None, aeFgColor=0x00D9DADC, aeBgColor=0x007586A0)
    numRadix_table = elemFindOrCreate(numRadix, "table", fo, po)
    attribGetOrSetDefault(numRadix_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2000, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2001, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2002, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2003, parentPos=4)
    elemCheckOrCreate_table_arrayElementImg(numRadix_table, fo, po, aeClass="Image", aeImageResID=-2095, parentPos=5)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[15,0,38,54], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21004, fo, po)

    return numText

def checkOrCreateParts_stdString_control(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of String Control type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,40], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    strRadix = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4104, \
      aeBounds=[21,4,33,10], aeImageResID=None, aeFgColor=0x00D9DADC, aeBgColor=0x007586A0)
    strRadix_table = elemFindOrCreate(strRadix, "table", fo, po)
    attribGetOrSetDefault(strRadix_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2104, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2105, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2106, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2107, parentPos=4)

    strRadixSh = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX_SHADOW, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4288, \
      aeBounds=[19,4,36,10], aeImageResID=None, aeFgColor=0x007586A0, aeBgColor=0x007586A0)
    strRadixSh_table = elemFindOrCreate(strRadixSh, "table", fo, po)
    attribGetOrSetDefault(strRadixSh_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2104, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2105, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2106, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2107, parentPos=4)

    aeObjFlags = 0x1932 # 6450
    if (parentObjFlags & 0x01) != 0:
        aeObjFlags &= ~0x1000
    strText = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.TEXT, aeObjFlags=aeObjFlags, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[21,4,36,96], aeImageResID=-239, aeFgColor=0x00FAFAFA, aeBgColor=0x00FAFAFA)
    strText_textRec = elemFindOrCreate(strText, "textRec", fo, po)
    attribGetOrSetDefault(strText_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "mode", fo, po), 8389636, fo, po)
    #elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "text", fo, po), "\""+strValue+"\"", fo, po) # TODO maybe fill default value?
    elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "bgColor", fo, po), "{:08X}".format(0x00FAFAFA), fo, po)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[17,0,40,100], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21701, fo, po)
    if (parentObjFlags & 0x01) == 0:
        elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "annexDDOFlag", fo, po), 2, fo, po)

    return strText

def checkOrCreateParts_stdString_indicator(RSRC, partsList, parentObjFlags, labelText, fo, po):
    """ Checks content of partsList element of String Indicator type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,40], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    strRadix = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4104, \
      aeBounds=[21,4,33,10], aeImageResID=None, aeFgColor=0x00D9DADC, aeBgColor=0x007586A0)
    strRadix_table = elemFindOrCreate(strRadix, "table", fo, po)
    attribGetOrSetDefault(strRadix_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2104, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2105, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2106, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(strRadix_table, fo, po, aeClass="Image", aeImageResID=-2107, parentPos=4)

    strRadixSh = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="multiCosm", \
      aePartID=PARTID.RADIX_SHADOW, aeObjFlags=6458, aeMasterPart=PARTID.FRAME, aeHowGrow=4288, \
      aeBounds=[19,4,36,10], aeImageResID=None, aeFgColor=0x007586A0, aeBgColor=0x007586A0)
    strRadixSh_table = elemFindOrCreate(strRadixSh, "table", fo, po)
    attribGetOrSetDefault(strRadixSh_table, "elements", 0, fo, po)

    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2104, parentPos=1)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2105, parentPos=2)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2106, parentPos=3)
    elemCheckOrCreate_table_arrayElementImg(strRadixSh_table, fo, po, aeClass="Image", aeImageResID=-2107, parentPos=4)

    aeObjFlags = 0x1932 # 6450
    if (parentObjFlags & 0x01) != 0 or True: # this function is for indicators, so always clear the flag
        aeObjFlags &= ~0x1000
    strText = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.TEXT, aeObjFlags=aeObjFlags, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[21,4,36,96], aeImageResID=-239, aeFgColor=0x00D2D2D2, aeBgColor=0x00D2D2D2)
    strText_textRec = elemFindOrCreate(strText, "textRec", fo, po)
    attribGetOrSetDefault(strText_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "mode", fo, po), 8389636, fo, po)
    #elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "text", fo, po), "\""+strValue+"\"", fo, po) # TODO maybe fill default value?
    elemTextGetOrSetDefault(elemFindOrCreate(strText_textRec, "bgColor", fo, po), "{:08X}".format(0x00D2D2D2), fo, po)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[17,0,40,100], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21702, fo, po)

    return strRadix

def checkOrCreateParts_stdClust_control(RSRC, partsList, parentObjFlags, labelText, corSz, fo, po):
    """ Checks content of partsList element of Cluster Control/Indicator type
    """
    nameLabel = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="label", \
      aePartID=PARTID.NAME_LABEL, aeObjFlags=1507654, aeMasterPart=PARTID.FRAME, aeHowGrow=4096,
      aeBounds=[0,0,15,corSz[1]], aeImageResID=-9, aeFgColor=0x01000000, aeBgColor=0x01000000)
    nameLabel_textRec = elemFindOrCreate(nameLabel, "textRec", fo, po)
    attribGetOrSetDefault(nameLabel_textRec, "class", "textHair", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "flags", fo, po), 1536, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "mode", fo, po), 17412, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "text", fo, po), "\""+labelText+"\"", fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(nameLabel_textRec, "bgColor", fo, po), "{:08X}".format(0x01000000), fo, po)

    contentArea = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.CONTENT_AREA, aeObjFlags=2359, aeMasterPart=PARTID.FRAME, aeHowGrow=240, \
      aeBounds=[21,4,corSz[0]-4,corSz[1]-4], aeImageResID=0, aeFgColor=0x00A6A6A6, aeBgColor=0x00A6A6A6)

    elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="cosm", \
      aePartID=PARTID.FRAME, aeObjFlags=2327, aeMasterPart=None, aeHowGrow=240, \
      aeBounds=[17,0,corSz[0],corSz[1]], aeImageResID=-412, aeFgColor=0x00B3B3B3, aeBgColor=0x01000000)

    # ANNEX properties taken from empty VI file created in LV14
    annexPart = elemCheckOrCreate_partList_arrayElement(partsList, fo, po, aeClass="annex", \
      aePartID=PARTID.ANNEX)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "refListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "hGrowNodeListLength", fo, po), 0, fo, po)
    elemTextGetOrSetDefault(elemFindOrCreate(annexPart, "rsrcID", fo, po), 21607, fo, po)

    return contentArea


def FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, \
      dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator):
    """ Gives expected size of the GUI element representing given types
    """
    dcoTypeDesc = None
    if dcoTypeID is not None and dcoTypeID in heapTypeMap.keys():
        dcoTypeDesc = heapTypeMap[dcoTypeID]
    if dcoTypeDesc is None:
        corBR = [corTL[0],corTL[1]]
    elif fpClass == "stdBool" and isIndicator == 0:
        corBR = [corTL[0]+48,corTL[1]+60]
    elif fpClass == "stdBool" and isIndicator != 0:
        corBR = [corTL[0]+38,corTL[1]+50]
    elif fpClass == "stdNum":
        corBR = [corTL[0]+38,corTL[1]+41]
    elif fpClass == "stdString":
        corBR = [corTL[0]+40,corTL[1]+100]
    elif fpClass == "stdClust":
        corBR = [corTL[0]+4,corTL[1]+4]
        corBR1 = corBR[1]
        for subTypeID in subTypeIDs:
            fpSubClass = DCO_recognize_class_from_dcoTypeID(RSRC, fo, po, subTypeID)
            corBR_end = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, \
                  corBR, fpSubClass, subTypeID, [], subTypeID, [], isIndicator)
            corBR = [corBR_end[0],corBR[1]]
            corBR1 = max(corBR1,corBR_end[1])
        corBR = [corBR[0]+4,corBR1+4]
    else:
        corBR = [corTL[0],corTL[1]]
    return corBR

def FPHb_elemCheckOrCreate_zPlaneList_DCO(RSRC, paneHierarchy_zPlaneList, fo, po, \
      heapTypeMap, corTL, defineDDO, fpClass, \
      dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, dcoConNum, isIndicator, dataSrcIdent):
    """ Checks or creates Front Panel componennt which represents specific DCO
    """
    typeCtlOrInd = "indicator" if isIndicator != 0 else "control"
    dcoTypeDesc = None
    if dcoTypeID is not None and dcoTypeID in heapTypeMap.keys():
        dcoTypeDesc = heapTypeMap[dcoTypeID]
    if dcoTypeDesc is None:
        eprint("{:s}: Warning: {} does not have dcoTypeID, not adding to FP"\
          .format(po.xml,dataSrcIdent))
        return None, None

    print("{:s}: Associating {} TypeDesc '{}' with FpDCO {} of class '{}'"\
      .format(po.xml,dataSrcIdent,dcoTypeDesc.get("Type"),typeCtlOrInd,fpClass))

    ddoTypeDesc = None
    if ddoTypeID is not None:
        ddoTypeDesc = heapTypeMap[ddoTypeID]

    labelText = dcoTypeDesc.get("Label")
    if fpClass == "stdBool":
        dcoObjFlags_val = 0x10200
        ddoObjFlags_val = 0 # 0x1: user input disabled
        if isIndicator != 0:
            dcoObjFlags_val |= 0x01
            ddoObjFlags_val |= 0x01
        if labelText is None: labelText = "Boolean"
    elif fpClass == "stdNum":
        dcoObjFlags_val = 0
        ddoObjFlags_val = 0x60042
        if isIndicator != 0:
            dcoObjFlags_val |= 0x01
            ddoObjFlags_val |= 0x01
        if labelText is None: labelText = "Numeric"
        stdNumMin, stdNumMax, stdNumInc = valueTypeGetDefaultRange(dcoTypeDesc.get("Type"), po)
    elif fpClass == "stdString":
        dcoObjFlags_val = 0
        ddoObjFlags_val = 0x0
        if isIndicator != 0:
            dcoObjFlags_val |= 0x01
            ddoObjFlags_val |= 0x01
        if labelText is None: labelText = "String"
    elif fpClass == "stdClust":
        dcoObjFlags_val = 0
        ddoObjFlags_val = 0x00004
        if isIndicator != 0:
            dcoObjFlags_val |= 0x01
            ddoObjFlags_val |= 0x01
        if labelText is None: labelText = "Cluster"
    else:
        dcoObjFlags_val = 0
        ddoObjFlags_val = 0
        if labelText is None: labelText = "Unknown"

    ddoClass_val = fpClass
    if defineDDO:
        dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement_DDO(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
          aeTypeID=dcoTypeID, aeObjFlags=dcoObjFlags_val, aeDdoClass=ddoClass_val, aeConNum=dcoConNum, aeTermListLength=1)
    else:
        dco_elem, ddo_elem = elemCheckOrCreate_zPlaneList_arrayElement(paneHierarchy_zPlaneList, fo, po, aeClass="fPDCO", \
          aeTypeID=dcoTypeID, aeObjFlags=dcoObjFlags_val, aeDdoClass=ddoClass_val, aeConNum=dcoConNum, aeTermListLength=1)

    if fpClass == "stdBool" and isIndicator == 0:
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val,
          aeBounds=corTL+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=0, aeMinButSize=[50,21], valueType=dcoTypeDesc.get("Type"))
        checkOrCreateParts_stdBool_control(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdBool" and isIndicator != 0:
        corTL_mv = [corTL[0],corTL[1]+32] # Bool indicator LED is moved strongly towards the left
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL_mv, fpClass, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val,
          aeBounds=corTL_mv+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=0, aeMinButSize=[17,17], valueType=dcoTypeDesc.get("Type"))
        checkOrCreateParts_stdBool_indicator(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdNum" and isIndicator == 0:
        corTL_mv = [corTL[0],corTL[1]+16] # Numeric control has arrows before component bounds
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL_mv, fpClass, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL_mv+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=2, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"), \
          aeStdNumMin=stdNumMin, aeStdNumMax=stdNumMax, aeStdNumInc=stdNumInc)
        checkOrCreateParts_stdNum_control(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdNum" and isIndicator != 0:
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=2, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"), \
          aeStdNumMin=stdNumMin, aeStdNumMax=stdNumMax, aeStdNumInc=stdNumInc)
        checkOrCreateParts_stdNum_indicator(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdString" and isIndicator == 0:
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=3, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"))
        checkOrCreateParts_stdString_control(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdString" and isIndicator != 0:
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL, fpClass, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        ddo_partsList, _ = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL+corBR, hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=3, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"))
        checkOrCreateParts_stdString_indicator(RSRC, ddo_partsList, ddoObjFlags_val, labelText, fo, po)
    elif fpClass == "stdClust": # Same code for Control and indicator
        corTL_mv = [corTL[0],corTL[1]+4] # Cluster panel frame
        corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, corTL_mv, fpClass, dcoTypeID, partTypeIDs, ddoTypeID, subTypeIDs, isIndicator)
        corSz = [corBR[0]-corTL_mv[0]+21, corBR[1]-corTL_mv[1]+12]
        ddo_partsList, ddo_paneHierarchy = elemCheckOrCreate_ddo_content(ddo_elem, fo, po, aeDdoObjFlags=ddoObjFlags_val, \
          aeBounds=corTL_mv+[corBR[0]+21,corBR[1]], hasParts=True, aeDdoTypeID=ddoTypeID, \
          aeMouseWheelSupport=0, aeMinButSize=None, valueType=dcoTypeDesc.get("Type"), aeSavedSize=[0,0,0,0])
        checkOrCreateParts_stdClust_control(RSRC, ddo_partsList, ddoObjFlags_val, labelText, corSz, fo, po)
        ddo_ph_zPlaneList, ddo_ph_partsList, ddo_ph_objFlags_val = \
              elemCheckOrCreate_paneHierarchy_content(ddo_paneHierarchy, fo, po,
              aeObjFlags=2494736, aeHowGrow=240, aeBounds=[21,4,corSz[0]-4,corSz[1]-4], hasParts=True,
              aePaneFlags=257, aeMinPaneSize=[1,1], aeOrigin=[-4,-4],
              aeDocBounds=[corSz[0]-62,-21,corSz[0]-62-60,corSz[1]+21], hasZPlane=True, aeImageResID=0)
        # Content of the 'paneHierarchy/partsList' element
        paneContent = checkOrCreateParts_ClusterPane(RSRC, ddo_ph_partsList, ddo_ph_objFlags_val, "Pane", corSz, fo, po)
        # Content of the 'paneHierarchy/zPlaneList' element
        corCtBL = [corBR[0]-corTL_mv[0]-21, corTL_mv[1]-4]
        corCtBL = [corCtBL[0]-4, corCtBL[1]]
        for subTypeID in subTypeIDs:
            fpSubClass = DCO_recognize_class_from_dcoTypeID(RSRC, fo, po, subTypeID)
            corBR = FPHb_elemCheckOrCreate_zPlaneList_DCO_size(RSRC, fo, po, heapTypeMap, [0,0], fpSubClass, \
                  dcoTypeID=subTypeID, partTypeIDs=[], ddoTypeID=subTypeID, subTypeIDs=[], isIndicator=isIndicator)
            corCtBL = [corCtBL[0]-corBR[0], corCtBL[1]]
            corCtBL_mv = [corCtBL[0], corCtBL[1]] # Make a copy to be sure coords are not modified by the function
            FPHb_elemCheckOrCreate_zPlaneList_DCO(RSRC, ddo_ph_zPlaneList, fo, po, heapTypeMap, corCtBL_mv, \
                  defineDDO=False, fpClass=fpSubClass, dcoTypeID=subTypeID, partTypeIDs=[], ddoTypeID=subTypeID, subTypeIDs=[], \
                  dcoConNum=dcoConNum, isIndicator=isIndicator, dataSrcIdent="{}.{}".format(dataSrcIdent,dcoTypeDesc.get("Type")))
    else:
        #TODO add more types
        corBR = [corTL[0],corTL[1]]
        dco_elem = None
        ddo_partsList = None
        eprint("{:s}: Warning: Heap dcoTypeDesc '{}' {} is not supported"\
          .format(po.xml,dcoTypeDesc.get("Type"),typeCtlOrInd))

    if defineDDO: # DDO level - order components horizontally
        if corBR[0] < 1066: # TODO this needs to be done without hard-coding width
            corTL[1] = corBR[1]
        else:
            corTL[1] = 0
            corTL[0] = corBR[0]
    else: # Nested levels - order components vertically
        if corBR[1] < 720: # TODO this needs to be done without hard-coding height
            corTL[0] = corBR[0]
        else:
            corTL[0] = 0
            corTL[1] = corBR[1]

    return dco_elem, ddo_partsList

def elemCheckOrCreate_bdroot_content(root, fo, po, aeObjFlags=None, hasPlanes=False, \
          hasNodes=False, hasSignals=False, aeBgColor=None, aeFirstNodeIdx=None,
          aeBounds=None, aeShortCount=None, aeClumpNum=None):
    """ Fils content of pre-created DDO tag
    """

    if aeObjFlags is not None:
        root_objFlags = elemFindOrCreate(root, "objFlags", fo, po, pos=0)
        elemTextGetOrSetDefault(root_objFlags, aeObjFlags, fo, po)

    zPlaneList = None
    if hasPlanes:
        zPlaneList = elemFindOrCreate(root, "zPlaneList", fo, po)
        attribGetOrSetDefault(zPlaneList, "elements", 0, fo, po)

    nodeList = None
    if hasNodes:
        nodeList = elemFindOrCreate(root, "nodeList", fo, po)
        attribGetOrSetDefault(nodeList, "elements", 0, fo, po)

    signalList = None
    if hasSignals:
        signalList = elemFindOrCreate(root, "signalList", fo, po)
        attribGetOrSetDefault(signalList, "elements", 0, fo, po)

    if aeBgColor is not None:
        bgColor = elemFindOrCreate(root, "bgColor", fo, po)
        elemTextGetOrSetDefault(bgColor, "{:08X}".format(aeBgColor), fo, po)

    if aeFirstNodeIdx is not None:
        firstNodeIdx = elemFindOrCreate(root, "firstNodeIdx", fo, po)
        elemTextGetOrSetDefault(firstNodeIdx, aeFirstNodeIdx, fo, po)

    # Now inside of the nodeList
    if nodeList is not None:
        nl_arrayElement = elemFindOrCreateWithAttribsAndTags(nodeList, "SL__arrayElement", \
          ( ("class", "sRN",), ), [], fo, po)

        if aeObjFlags is not None:
            arrayElement_objFlags = elemFindOrCreate(nl_arrayElement, "objFlags", fo, po, pos=0)
            elemTextGetOrSetDefault(arrayElement_objFlags, aeObjFlags, fo, po)

        arrayElement_termList = elemFindOrCreate(nl_arrayElement, "termList", fo, po)
        attribGetOrSetDefault(arrayElement_termList, "elements", 0, fo, po)

        if aeBounds is not None:
            arrayElement_bounds = elemFindOrCreate(nl_arrayElement, "bounds", fo, po)
            elemTextGetOrSetDefault(arrayElement_bounds, aeBounds, fo, po)

        if aeShortCount is not None:
            arrayElement_shortCount = elemFindOrCreate(nl_arrayElement, "shortCount", fo, po)
            elemTextGetOrSetDefault(arrayElement_shortCount, aeShortCount, fo, po)

        if aeClumpNum is not None:
            arrayElement_clumpNum = elemFindOrCreate(nl_arrayElement, "clumpNum", fo, po)
            elemTextGetOrSetDefault(arrayElement_clumpNum, aeClumpNum, fo, po)

    return zPlaneList, arrayElement_termList, signalList

def FPHb_Fix(RSRC, FPHP, ver, fo, po):
    block_name = "FPHb"

    attribGetOrSetDefault(FPHP, "Index", 0, fo, po)
    sect_format = FPHP.get("Format")
    if sect_format not in ("xml",):
        FPHP.set("Format","xml")
        if len(RSRC.findall("./"+block_name+"/Section")) <= 1:
            snum_str = ""
        else:
            if sect_index >= 0:
                snum_str = str(sect_index)
            else:
                snum_str = 'm' + str(-sect_index)
        fname_base = "{:s}_{:s}{:s}".format(po.filebase, block_name, snum_str)
        FPHP.set("File","{:s}.xml".format(fname_base))
        fo[FUNC_OPTS.changed] = True

    rootObject = elemFindOrCreate(FPHP, "SL__rootObject", fo, po)
    attribGetOrSetDefault(rootObject, "class", "oHExt", fo, po)
    attribGetOrSetDefault(rootObject, "uid", 1, fo, po)

    root = elemFindOrCreate(rootObject, "root", fo, po)
    attribGetOrSetDefault(root, "class", "supC", fo, po)
    attribGetOrSetDefault(root, "uid", 1, fo, po)

    pBounds = elemFindOrCreate(rootObject, "pBounds", fo, po)
    elemTextGetOrSetDefault(pBounds, [46,0,681,1093], fo, po)
    dBounds = elemFindOrCreate(rootObject, "dBounds", fo, po)
    elemTextGetOrSetDefault(dBounds, [0,0,0,0], fo, po)

    origin = elemFindOrCreate(rootObject, "origin", fo, po)
    elemTextGetOrSetDefault(origin, [327,105], fo, po)

    instrStyle = elemFindOrCreate(rootObject, "instrStyle", fo, po)
    elemTextGetOrSetDefault(instrStyle, 31, fo, po)

    blinkList = elemFindOrCreate(rootObject, "blinkList", fo, po)
    attribGetOrSetDefault(blinkList, "elements", 0, fo, po)

    # Now content of the 'root' element

    root_partsList, root_paneHierarchy = elemCheckOrCreate_ddo_content(root, fo, po,
      aeDdoObjFlags=65536, aeBounds=[0,0,0,0], aeMouseWheelSupport=0, \
      valueType="Cluster", aeSavedSize=[0,0,0,0])

    root_conPane = elemFindOrCreate(root, "conPane", fo, po)
    attribGetOrSetDefault(root_conPane, "class", "conPane", fo, po)
    attribGetOrSetDefault(root_conPane, "uid", 1, fo, po)

    root_keyMappingList = elemFindOrCreate(root, "keyMappingList", fo, po)
    attribGetOrSetDefault(root_keyMappingList, "class", "keyMapList", fo, po)
    attribGetOrSetDefault(root_keyMappingList, "uid", 1, fo, po)
    attribGetOrSetDefault(root_keyMappingList, "ScopeInfo", 0, fo, po)

    # Now content of the 'root/conPane' element

    root_conPane_conId = elemFindOrCreate(root_conPane, "conId", fo, po)

    conCount = getConnectorPortsFixedCount(RSRC, ver, fo, po)
    #TODO we could set conId better by considering inputs vs outputs
    if conCount <= 1: conId = 4800
    elif conCount <= 2: conId = 4801
    elif conCount <= 3: conId = 4803
    elif conCount <= 4: conId = 4806
    elif conCount <= 5: conId = 4807
    elif conCount <= 6: conId = 4810
    elif conCount <= 7: conId = 4811
    elif conCount <= 8: conId = 4812
    elif conCount <= 9: conId = 4813
    elif conCount <= 10: conId = 4826
    elif conCount <= 11: conId = 4829
    elif conCount <= 12: conId = 4815
    elif conCount <= 16: conId = 4833
    elif conCount <= 20: conId = 4834
    elif conCount <= 28: conId = 4835
    else: conId = 4815 # Most widely used
    elemTextGetOrSetDefault(root_conPane_conId, conId, fo, po)

    root_conPane_cons = elemFindOrCreate(root_conPane, "cons", fo, po)
    attribGetOrSetDefault(root_conPane_cons, "elements", 0, fo, po)
    # The rest of 'root/conPane' will be filled later, after UIDs are made unique

    # Now content of the 'root/paneHierarchy' element

    objFlags = 0x050d51 # in new empty VI it's 0x0260834
    if False: #TODO if horiz scrollbar disabled
        objFlags |= 0x0004
    if False: #TODO if vert scrollbar disabled
        objFlags |= 0x0008

    paneHierarchy_zPlaneList, paneHierarchy_partsList, paneHierarchy_objFlags_val = \
          elemCheckOrCreate_paneHierarchy_content(root_paneHierarchy, fo, po,
          aeObjFlags=objFlags, aeHowGrow=240, aeBounds=[46,0,681,1093], hasParts=True,
          aePaneFlags=331089, aeMinPaneSize=[1,1],
          aeDocBounds=[0,0,619,1077], hasZPlane=True, aeImageResID=0)

    # Now content of the 'root/paneHierarchy/partsList' element
    paneContent = checkOrCreateParts_RootPane(RSRC, paneHierarchy_partsList, paneHierarchy_objFlags_val, "Pane", fo, po)

    # Now content of the 'root/paneHierarchy/zPlaneList' element

    DTHP_typeDescSlice = RSRC.find("./DTHP/Section/TypeDescSlice")
    if DTHP_typeDescSlice is not None:
        DTHP_indexShift = DTHP_typeDescSlice.get("IndexShift")
        if DTHP_indexShift is not None:
            DTHP_indexShift = int(DTHP_indexShift, 0)
        DTHP_tdCount = DTHP_typeDescSlice.get("Count")
        if DTHP_tdCount is not None:
            DTHP_tdCount = int(DTHP_tdCount, 0)
    else:
        raise NotImplementedError("DTHP should've been already re-created at this point.")

    # recover FP DCOs from a list within DFDS
    TM80_IndexShift = None
    TM80 = RSRC.find("./TM80/Section")
    if TM80 is not None:
        TM80_IndexShift = TM80.get("IndexShift")
        if TM80_IndexShift is not None:
            TM80_IndexShift = int(TM80_IndexShift, 0)

    FpDCOList = getFpDCOTableAsList(RSRC, po, TM80_IndexShift=TM80_IndexShift)

    # recover more data on FP DCOs from Heap TDs
    # Heap Types first store a list of TypeDescs used in FP, then a list of TDs used in BD
    # We need to map the first part to the DCOs we have. Connectors may be helpful here, as if they
    # are set, then they store TypeID values for types associated to the DCOs.
    heapTypeMap = {htId+1:getConsolidatedTopType(RSRC, DTHP_indexShift+htId, po) for htId in range(DTHP_tdCount)}

    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is not None:
        VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    else:
        VCTP_TypeDescList = []
        VCTP_FlatTypeDescList = []
    usedTypeID = 1 # Heap TypeID values start with 1
    # Figure out Heap Types range for each DCO
    for DCO in reversed(FpDCOList):
        dcoTDCount = 0
        DCOInfo = None
        if usedTypeID in heapTypeMap:
            dcoTDCount, DCOInfo = DCO_recognize_from_typeIDs(RSRC, fo, po, DTHP_indexShift+usedTypeID-1, DTHP_indexShift+DTHP_tdCount-1, VCTP_TypeDescList, VCTP_FlatTypeDescList)
        if DCOInfo is not None:
            # Switch typeID values to Heap Type IDs
            DCOInfo['dcoTypeID'] = DCOInfo['dcoTypeID']-DTHP_indexShift+1
            DCOInfo['partTypeIDs'] = [ typeID-DTHP_indexShift+1 for typeID in DCOInfo['partTypeIDs'] ]
            DCOInfo['ddoTypeID'] = DCOInfo['ddoTypeID']-DTHP_indexShift+1
            DCOInfo['subTypeIDs'] = [ typeID-DTHP_indexShift+1 for typeID in DCOInfo['subTypeIDs'] ]
        else:
            eprint("{:s}: Warning: Heap TypeDesc {} expected for DCO{} does not match known TD patterns"\
              .format(po.xml,usedTypeID,DCO['dcoIndex']))
            DCOInfo = { 'fpClass': "stdNum", 'dcoTypeID': usedTypeID, 'partTypeIDs': [], 'ddoTypeID': usedTypeID, 'subTypeIDs': [] }
            dcoTDCount = 1
        # Store the values inside DCO
        DCO.update(DCOInfo)
        usedTypeID += dcoTDCount

    corTL = [0,0] # Coordinates top left
    for DCO in reversed(FpDCOList):
        FPHb_elemCheckOrCreate_zPlaneList_DCO(RSRC, paneHierarchy_zPlaneList, fo, po, heapTypeMap, corTL, \
              defineDDO=True, fpClass=DCO['fpClass'], dcoTypeID=DCO['dcoTypeID'], \
              partTypeIDs=DCO['partTypeIDs'], ddoTypeID=DCO['ddoTypeID'], subTypeIDs=DCO['subTypeIDs'], \
              dcoConNum=DCO['conNum'], isIndicator=DCO['isIndicator'], dataSrcIdent="DCO{}".format(DCO['dcoIndex']))

    # Get expected grid alignment
    LVSR_parUnknown = RSRC.find("./LVSR/Section/Unknown")
    if LVSR_parUnknown is not None:
        gridDelta = LVSR_parUnknown.get("AlignGridFP")
    if gridDelta is not None:
        gridDelta = int(gridDelta,0)
    if gridDelta is None or gridDelta < 4 or gridDelta > 256:
        gridDelta = 12 # default value in case alignment from LVSR is suspicious
    # Get window content bounds
    paneContentBounds = paneContent.find("./bounds")
    if paneContentBounds is not None:
        paneContentBounds = paneContentBounds.text
    if paneContentBounds is not None:
        paneContentBounds = strToList(paneContentBounds)
    if paneContentBounds is None:
        paneContentBounds = [0,0,622,622]
    windowWidth = paneContentBounds[3] - paneContentBounds[1]
    # Re-compute positions of DCOs so they do not overlap and fit the window
    zPlaneList_elems = paneHierarchy_zPlaneList.findall("./SL__arrayElement[@class='fPDCO'][@uid]")
    i = 1
    while i < len(zPlaneList_elems):
        dco_elem = zPlaneList_elems[i]
        bounds_elem = dco_elem.find("./ddo/bounds")
        if bounds_elem is None:
            i += 1
            continue
        eBounds = bounds_elem.text
        if eBounds is not None:
            eBounds = strToList(eBounds)
        if eBounds is None:
            eBounds = [0,0,16,16]
            eprint("{:s}: Warning: Could not read bounds of FpDCO"\
              .format(po.xml))
        eMoved = False
        for k in range(0,i):
            overlap_elem = zPlaneList_elems[k]
            oBounds = overlap_elem.find("./ddo/bounds")
            if oBounds is not None:
                oBounds = oBounds.text
            if oBounds is not None:
                oBounds = strToList(oBounds)
            if oBounds is None:
                oBounds = [0,0,16,16]
            while boundsOverlap(eBounds, oBounds):
                eMoved = True
                eBounds[1] += gridDelta
                eBounds[3] += gridDelta
                if eBounds[3] >= windowWidth:
                    eBounds[3] -= eBounds[0]
                    eBounds[1] = 0
                    eBounds[0] += gridDelta
                    eBounds[2] += gridDelta
                    if eBounds[3] >= windowWidth:
                        break # Safety check for incredibly huge components (or small windows)
        if eMoved:
            elemTextSetValue(bounds_elem, eBounds, fo, po)
            continue
        i += 1
    return fo[FUNC_OPTS.changed]

def LIvi_Fix(RSRC, LIvi, ver, fo, po):
    LVIN = LIvi.find("LVIN")
    if LVIN is None:
        LVIN = ET.SubElement(LIvi, "LVIN")
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def LIfp_Fix(RSRC, LIfp, ver, fo, po):
    FPHP = LIfp.find("FPHP")
    if FPHP is None:
        FPHP = ET.SubElement(LIfp, "FPHP")
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def LIbd_Fix(RSRC, LIbd, ver, fo, po):
    BDHP = LIbd.find("BDHP")
    if BDHP is None:
        BDHP = ET.SubElement(LIbd, "BDHP")
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def TM80_Fix(RSRC, DSTM, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def intRangesExcludeOne(iRanges, excludeIndex):
    if excludeIndex is None:
        return iRanges
    nRanges = []
    for rng in iRanges:
        if excludeIndex < rng.min or excludeIndex > rng.max:
            nRanges.append(rng)
            continue
        nRng = SimpleNamespace(min=rng.min,max=excludeIndex-1)
        if nRng.max - nRng.min >= 0:
            nRanges.append(nRng)
        nRng = SimpleNamespace(min=excludeIndex+1,max=rng.max)
        if nRng.max - nRng.min >= 0:
            nRanges.append(nRng)
    return nRanges

def intRangesExcludeBelow(iRanges, excludeIndex):
    if excludeIndex is None:
        return iRanges
    nRanges = intRangesExcludeOne(iRanges, excludeIndex)
    return [ rng for rng in nRanges if rng.min > excludeIndex ]

def intRangesExcludeBetween(iRanges, excludeIndexMin, excludeIndexMax):
    if excludeIndexMin is None or excludeIndexMax is None:
        return iRanges
    nRanges = intRangesExcludeOne(iRanges, excludeIndexMin)
    nRanges = intRangesExcludeOne(nRanges, excludeIndexMax)
    return [ rng for rng in nRanges if (rng.max < excludeIndexMin) or (rng.min > excludeIndexMax) ]

def intRangesOneContaining(iRanges, leaveIndex):
    if leaveIndex is None:
        return iRanges
    nRanges = []
    for rng in iRanges:
        if leaveIndex < rng.min or leaveIndex > rng.max:
            continue
        nRanges.append(nRng)
    if len(nRanges) < 1:
        return iRanges
    return nRanges

def getDCOMappingForIntField(RSRC, dcoFieldName, po, TM80_IndexShift=None, FpDCOTable_TypeID=None):
    """ Returns mapping between DCO Indexes and specified integer field from the DCOs

    If given dcoFieldName represents TMI, converts it to TypeID.
    """
    if TM80_IndexShift is None:
        TM80 = RSRC.find("./TM80/Section")
        if TM80 is not None:
            TM80_IndexShift = TM80.get("IndexShift")
            if TM80_IndexShift is not None:
                TM80_IndexShift = int(TM80_IndexShift, 0)
    dcoMapping = {}
    DCO_fields = [ field[0] for field in LVparts.DCO._fields_ ]
    FpDCOTable = getFpDCOTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, FpDCOTable_TypeID=FpDCOTable_TypeID)
    if FpDCOTable is not None:
            for FpDCO in FpDCOTable.findall("./RepeatedBlock/Cluster"):
                FpDCO_FieldValue = None
                # List fields without comments
                FpDCO_FieldList = list(filter(lambda f: f.tag is not ET.Comment, FpDCO.findall("./*")))
                val = FpDCO_FieldList[DCO_fields.index(dcoFieldName)].text
                if val is not None:
                    val = int(val,0)
                    if dcoFieldName.endswith("TMI"):
                        assert(TM80_IndexShift is not None) # Otherwise we wouldn't have DCO list at all
                        FpDCO_FieldValue = TM80_IndexShift + (val & 0xFFFFFF)
                    else:
                        FpDCO_FieldValue = val
                idx = FpDCO_FieldList[DCO_fields.index('dcoIndex')].text
                idx = int(idx,0)
                dcoMapping[idx] = FpDCO_FieldValue
    return dcoMapping

def getTypeDescFromMapUsingList(FlatTypeDescList, TDTopMap, po):
    """ Retrieves TypeDesc element, using mapping list and TD list

    Returns entry from FlatTypeDescList, and position of that entry.
    """
    TDTopMap_Index = TDTopMap.get("Index")
    if TDTopMap_Index is not None:
        TDTopMap_Index = int(TDTopMap_Index, 0)
    FlatTypeID = TDTopMap.get("FlatTypeID")
    if FlatTypeID is None:
        FlatTypeID = TDTopMap.get("TypeID") # For map entries within Clusters
    if FlatTypeID is not None:
        FlatTypeID = int(FlatTypeID, 0)
    if FlatTypeID is None:
        if (po.verbose > 2):
            print("{:s}: TypeDesc {} mapping entry is damaged"\
                .format(po.xml,TDTopMap_Index))
        return None, TDTopMap_Index, FlatTypeID
    if FlatTypeID >= 0 and FlatTypeID < len(FlatTypeDescList):
        TypeDesc = FlatTypeDescList[FlatTypeID]
    else:
        if (po.verbose > 2):
            print("{:s}: TypeDesc {} Flat TypeID {} is missing from flat list"\
                .format(po.xml,TDTopMap_Index,FlatTypeID))
        TypeDesc = None
    return TypeDesc, TDTopMap_Index, FlatTypeID

def getTypeDescFromIDUsingLists(TypeDescMap, FlatTypeDescList, typeID, po):
    """ Retrieves TypeDesc element, using mapping list and TD list

    Returns entry from FlatTypeDescList, and position of that entry.
    """
    for TDTopMap in TypeDescMap:
        TDTopMap_Index = TDTopMap.get("Index")
        if TDTopMap_Index is not None:
            TDTopMap_Index = int(TDTopMap_Index, 0)
        if TDTopMap_Index != typeID:
            continue
        TypeDesc, TDTopMap_Index, FlatTypeID = getTypeDescFromMapUsingList(FlatTypeDescList, TDTopMap, po)
        return TypeDesc, FlatTypeID
    return None, None

def getMaxIndexFromList(elemList, fo, po):
    val = 1
    for elem in elemList:
        elemIndex = elem.get("Index")
        if elemIndex is not None:
            elemIndex = int(elemIndex, 0)
        if elemIndex is not None:
            val = max(val, elemIndex)
    return val

def TypeDesc_find_unused_ranges(RSRC, fo, po, skipRm=[], VCTP_TypeDescList=None, VCTP_FlatTypeDescList=None):
    """ Searches through all TDs, looking for unused items

    Skips removal of items for specified groups - often we will want the groups to include TM80.
    """
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP_TypeDescList is None:
        if VCTP is not None:
            VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        else:
            VCTP_TypeDescList = []
    if VCTP_FlatTypeDescList is None:
        if VCTP is not None:
            VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    # Set min possible value; we will increase it shortly
    # and max acceptable value; we will decrease it shortly
    properMax = getMaxIndexFromList(VCTP_TypeDescList, fo, po)
    unusedRanges = [ SimpleNamespace(min=1,max=properMax) ]
    # find unused TD ranges
    if True:
        # We need TM80 to convert TMIs into TypeIDs
        TM80_IndexShift = None
        TM80 = RSRC.find("./TM80/Section")
        if TM80 is not None:
            TM80_IndexShift = TM80.get("IndexShift")
            if TM80_IndexShift is not None:
                TM80_IndexShift = int(TM80_IndexShift, 0)
    if "TM80" not in skipRm:
        if TM80 is not None:
            TM80_Clients = TM80.findall("./Client")
            if len(TM80_Clients) > 0:
                unusedRanges = intRangesExcludeBetween(unusedRanges, TM80_IndexShift, TM80_IndexShift+len(TM80_Clients)-1)
    if "DTHP" not in skipRm:
        DTHP_indexShift = None
        DTHP_tdCount = None
        DTHP_typeDescSlice = RSRC.find("./DTHP/Section/TypeDescSlice")
        if DTHP_typeDescSlice is not None:
            DTHP_indexShift = DTHP_typeDescSlice.get("IndexShift")
            if DTHP_indexShift is not None:
                DTHP_indexShift = int(DTHP_indexShift, 0)
            DTHP_tdCount = DTHP_typeDescSlice.get("Count")
            if DTHP_tdCount is not None:
                DTHP_tdCount = int(DTHP_tdCount, 0)
        if (DTHP_indexShift is not None) and (DTHP_tdCount is not None):
            unusedRanges = intRangesExcludeBetween(unusedRanges, DTHP_indexShift, DTHP_indexShift+DTHP_tdCount-1)
    if "CONP" not in skipRm:
        # Exclude TypeDesc pointed by CONP
        CONP_TypeID = None
        CONP_TypeDesc = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDesc is not None:
            CONP_TypeID = CONP_TypeDesc.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
        unusedRanges = intRangesExcludeOne(unusedRanges, CONP_TypeID)
        if (po.verbose > 3):
            print("{:s}: After CONP exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "CPC2" not in skipRm:
        # Exclude TypeDesc pointed by CPC2
        CPC2_TypeID = None
        CPC2_TypeDesc = RSRC.find("./CPC2/Section/TypeDesc")
        if CPC2_TypeDesc is not None:
            CPC2_TypeID = CPC2_TypeDesc.get("TypeID")
            if CPC2_TypeID is not None:
                CPC2_TypeID = int(CPC2_TypeID, 0)
        unusedRanges = intRangesExcludeOne(unusedRanges, CPC2_TypeID)
        if (po.verbose > 3):
            print("{:s}: After CPC2 exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "PFTD" not in skipRm:
        # Exclude TypeDesc pointed by PFTD
        FPTD_TypeID = None
        FPTD_TypeDesc = RSRC.find("./FPTD/Section/TypeDesc")
        if FPTD_TypeDesc is not None:
            FPTD_TypeID = FPTD_TypeDesc.get("TypeID")
            if FPTD_TypeID is not None:
                FPTD_TypeID = int(FPTD_TypeID, 0)
        unusedRanges = intRangesExcludeOne(unusedRanges, FPTD_TypeID)
        if (po.verbose > 3):
            print("{:s}: After PFTD exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    # We need DSInit for several exclusions below
    DSInit = getDSInitRecord(RSRC, po)
    if "DSInit" not in skipRm:
        # Exclude TypeDesc with DSInit
        DSInit_TypeID = None
        if DSInit is not None:
            DSInit_TypeID = DSInit.get("TypeID")
        if DSInit_TypeID is not None:
            DSInit_TypeID = int(DSInit_TypeID, 0)
        unusedRanges = intRangesExcludeOne(unusedRanges, DSInit_TypeID)
    if "HiliteTb" not in skipRm:
        # Exclude TypeDesc which contain Hilite Table
        HiliteTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.hiliteTableTMI, po, DSInit=DSInit)
            if val_TMI is not None and val_TMI >= 0:
                HiliteTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, HiliteTable_TypeID)
    if True:
        # We need probe table index not only to exclude it, but to access the items inside
        ProbeTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.probeTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ProbeTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
    if "ProbeTb" not in skipRm:
        # Exclude TypeDesc which contain Probe Table
        unusedRanges = intRangesExcludeOne(unusedRanges, ProbeTable_TypeID)
    if "FpDcoTb" not in skipRm:
        # Exclude TypeDesc which contain FP DCO Table
        FpDCOTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.fpdcoTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                FpDCOTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, FpDCOTable_TypeID)
        if (po.verbose > 3):
            print("{:s}: After FP DCO Table exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "ClumpQE" not in skipRm:
        # Exclude TypeDesc which contain Clump QE Alloc
        ClumpQEAlloc_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.clumpQEAllocTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ClumpQEAlloc_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, ClumpQEAlloc_TypeID)
    if "VIParamTb" not in skipRm:
        # Exclude TypeDesc which contain VI Param Table
        VIParamTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.viParamTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                VIParamTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, VIParamTable_TypeID)
        if (po.verbose > 3):
            print("{:s}: After VI Param Table exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "ExtraDCOInfo" not in skipRm:
        # Exclude TypeDesc which contain Extra DCO Info
        ExtraDCOInfo_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.extraDCOInfoTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                ExtraDCOInfo_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, ExtraDCOInfo_TypeID)
    if "IOConnIdx" not in skipRm:
        # Exclude TypeDesc which contain IO Conn Idx
        IOConnIdx_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.localInputConnIdxTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                IOConnIdx_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, IOConnIdx_TypeID)
    if "IntHiliteTb" not in skipRm:
        # Exclude TypeDesc which contain InternalHiliteTableHandleAndPtr
        InternalHiliteTableHandleAndPtr_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.internalHiliteTableHandleAndPtrTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                InternalHiliteTableHandleAndPtr_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, InternalHiliteTableHandleAndPtr_TypeID)
    if "SubVIPatchTags" not in skipRm:
        # Exclude TypeDesc which contain SubVI Patch Tags
        SubVIPatchTags_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.subVIPatchTagsTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SubVIPatchTags_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, SubVIPatchTags_TypeID)
    if "SubVIPatch" not in skipRm:
        # Exclude TypeDesc which contain SubVI Patch
        SubVIPatch_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.subVIPatchTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SubVIPatch_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, SubVIPatch_TypeID)
        if (po.verbose > 3):
            print("{:s}: After SubVI Patch exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "EnpdTdOffsets" not in skipRm:
        # Exclude TypeDesc which contain Enpd Td Offsets
        EnpdTdOffsets_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.enpdTdOffsetsTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                EnpdTdOffsets_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, EnpdTdOffsets_TypeID)
    if "SpDdoTable" not in skipRm:
        # Exclude TypeDesc which contain Sp DDO Table
        SpDDOTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.spDDOTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                SpDDOTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, SpDDOTable_TypeID)
    if "StepIntoNodeIdxTb" not in skipRm:
        # Exclude TypeDesc which contain StepInto Node Idx Table
        StepIntoNodeIdxTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.stepIntoNodeIdxTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                StepIntoNodeIdxTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, StepIntoNodeIdxTable_TypeID)
    if "HiliteIdxTable" not in skipRm:
        # Exclude TypeDesc which contain Hilite Idx Table
        HiliteIdxTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.hiliteIdxTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                HiliteIdxTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, HiliteIdxTable_TypeID)
    if "GCodeProfileResultTb" not in skipRm:
        # Exclude TypeDesc which contain Generated Code Profile Result Table
        GeneratedCodeProfileResultTable_TypeID = None
        if TM80_IndexShift is not None:
            val_TMI = getDSInitEntry(RSRC, DSINIT.generatedCodeProfileResultTableTMI, po, DSInit=DSInit)
            if val_TMI is not None:
                GeneratedCodeProfileResultTable_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
        unusedRanges = intRangesExcludeOne(unusedRanges, GeneratedCodeProfileResultTable_TypeID)
        if (po.verbose > 3):
            print("{:s}: After GCPR Table exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "FpDcoTb" not in skipRm:
        # Exclude TypeDesc values pointed to by DCOs
        DCO_fields = [ field[0] for field in LVparts.DCO._fields_ ]
        FpDCOTable = getFpDCOTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, FpDCOTable_TypeID=FpDCOTable_TypeID)
        if FpDCOTable is not None and TM80_IndexShift is not None:
            for FpDCO in FpDCOTable.findall("./RepeatedBlock/Cluster"):
                FpDCOFlags_TypeID = None
                FpDCODefaultDataTMI_TypeID = None
                FpDCOExtraData_TypeID = None
                # List fields without comments
                FpDCO_FieldList = list(filter(lambda f: f.tag is not ET.Comment, FpDCO.findall("./*")))
                val_TMI = FpDCO_FieldList[DCO_fields.index('flagTMI')].text
                if val_TMI is not None:
                    val_TMI = int(val_TMI,0)
                    FpDCOFlags_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                val_TMI = FpDCO_FieldList[DCO_fields.index('defaultDataTMI')].text
                if val_TMI is not None:
                    val_TMI = int(val_TMI,0)
                    FpDCODefaultDataTMI_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                val_TMI = FpDCO_FieldList[DCO_fields.index('extraDataTMI')].text
                if val_TMI is not None:
                    val_TMI = int(val_TMI,0)
                    FpDCOExtraData_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                idx = FpDCO_FieldList[DCO_fields.index('dcoIndex')].text
                idx = int(idx,0)
                if (po.verbose > 3):
                    print("{:s}: After DCO{} check, excluding from unused TD ranges: {} {} {}"\
                        .format(po.xml,idx,FpDCOFlags_TypeID,FpDCODefaultDataTMI_TypeID,FpDCOExtraData_TypeID))
                unusedRanges = intRangesExcludeOne(unusedRanges, FpDCOFlags_TypeID)
                unusedRanges = intRangesExcludeOne(unusedRanges, FpDCODefaultDataTMI_TypeID)
                unusedRanges = intRangesExcludeOne(unusedRanges, FpDCOExtraData_TypeID)
    if "ProbePoints" not in skipRm:
        # Exclude TypeDesc values pointed to by ProbePoints
        ProbeTable = getProbeTable(RSRC, po, TM80_IndexShift=TM80_IndexShift, ProbeTable_TypeID=ProbeTable_TypeID)
        if ProbeTable is not None and TM80_IndexShift is not None:
            ProbeTable_FieldList = list(filter(lambda f: f.tag is not ET.Comment, ProbeTable.findall("./RepeatedBlock/I32")))
            for i in range(len(ProbeTable_FieldList)//2):
                val_TMI = ProbeTable_FieldList[2*i+1].text
                if val_TMI is not None:
                    val_TMI = int(val_TMI, 0)
                if val_TMI < 1:
                    val_TMI = None
                ProbePoint_TypeID = None
                if val_TMI is not None:
                    ProbePoint_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                unusedRanges = intRangesExcludeOne(unusedRanges, ProbePoint_TypeID)
        if (po.verbose > 3):
            print("{:s}: After ProbePoints exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    if "BFAL" not in skipRm:
        # Exclude TypeDesc values pointed to by BFAL
        if TM80_IndexShift is not None:
            for BFAL_TypeMap in RSRC.findall("./BFAL/Section/TypeMap"):
                val_TMI = BFAL_TypeMap.get("TMI")
                if val_TMI is not None:
                    val_TMI = int(val_TMI, 0)
                BFAL_TypeID = None
                if val_TMI is not None:
                    BFAL_TypeID = TM80_IndexShift + (val_TMI & 0xFFFFFF)
                unusedRanges = intRangesExcludeOne(unusedRanges, BFAL_TypeID)
        if (po.verbose > 3):
            print("{:s}: After BFAL exclusion, unused TD ranges: {}"\
                .format(po.xml,unusedRanges))
    return unusedRanges

def DCO_recognize_class_from_single_typeID(RSRC, fo, po, typeID):
    """ Recognizes DCO class using only TypeID of DCO as input

    This should be used only if more TypeIDs are not available and there is no other way than to use this simplified method.
    Returns the DCO class name.
    """
    # Get DCO TypeDesc
    dcoTypeDesc = getConsolidatedTopType(RSRC, typeID, po)
    # Recognize the DCO
    if dcoTypeDesc.get("Type") == "Boolean":
        return "stdBool"
    if dcoTypeDesc.get("Type").startswith("Num"):
        return "stdNum"
    if dcoTypeDesc.get("Type") == "String":
        return "stdString"
    if dcoTypeDesc.get("Type").startswith("UnitUInt"):
        return "radioClust"
    if dcoTypeDesc.get("Type") == "Cluster":
        return "stdClust"
    # No control recognized
    return None

def DCO_recognize_class_from_dcoTypeID(RSRC, fo, po, dcoTypeID):
    """ Recognizes DCO class using only Heap typeID of the DCO as input
    """
    DTHP_typeDescSlice = RSRC.find("./DTHP/Section/TypeDescSlice")
    if DTHP_typeDescSlice is not None:
        DTHP_indexShift = DTHP_typeDescSlice.get("IndexShift")
        if DTHP_indexShift is not None:
            DTHP_indexShift = int(DTHP_indexShift, 0)
    if DTHP_indexShift is None:
        return None
    typeID = DTHP_indexShift+dcoTypeID-1
    return DCO_recognize_class_from_single_typeID(RSRC, fo, po, typeID)

def DCO_recognize_from_typeIDs(RSRC, fo, po, typeID, endTypeID, VCTP_TypeDescList, VCTP_FlatTypeDescList):
    """ Recognizes DCO from its data space, starting at given typeID

    Returns amount of typeID entries used by that DCO, and DCO information dict.
    TypeID values within the DCO information dict are Top Types in dange between typeID and endTypeID, including boundary values.
    """
    VCTP = RSRC.find("./VCTP/Section")
    if VCTP is None or endTypeID < typeID:
        return 0, None
    # Get list of Flat TypeDescs
    flatTypeIDList = []
    for subTypeID in range(typeID, endTypeID+1):
        _, flatSubTypeID = getConsolidatedTopTypeAndID(RSRC, subTypeID, po, VCTP=VCTP)
        assert(flatSubTypeID is not None)
        flatTypeIDList.append(flatSubTypeID)
    tdCount, DCOShiftInfo = DCO_recognize_TDs_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList)
    if DCOShiftInfo is None:
        return 0, None
    # Convert TypeID Shifts to Top TypeIDs
    dcoTypeID = typeID + DCOShiftInfo['dcoTypeID']
    partTypeIDs = [ typeID + typeIndex for typeIndex in DCOShiftInfo['partTypeIDs'] ]
    subTypeIDs = [ typeID + typeIndex for typeIndex in DCOShiftInfo['subTypeIDs'] ]
    ddoTypeID = typeID + DCOShiftInfo['ddoTypeID']
    DCOTopInfo = { 'fpClass': DCOShiftInfo['fpClass'], 'dcoTypeID': dcoTypeID, 'partTypeIDs': partTypeIDs, 'ddoTypeID': ddoTypeID, 'subTypeIDs': subTypeIDs }
    return tdCount, DCOTopInfo

def DCO_recognize_TDs_from_flat_list(RSRC, fo, po, VCTP_FlatTypeDescList, flatTypeIDList):
    """ Recognizes DCO from its data space, using given list of FlatTypeIDs

    Returns amount of FlatTypeID entries used by that DCO, and DCO information dict.
    This is the most important function for re-creating DTHP and FPHp sections.
    """
    if len(flatTypeIDList) < 2:
        return 0, None
    # Get the DCO TypeDecs
    dcoFlatTypeID = flatTypeIDList[0]
    dcoTypeDesc = getConsolidatedFlatType(RSRC, dcoFlatTypeID, po)
    # Get the next TypeDesc
    n1FlatTypeID = flatTypeIDList[1]
    n1TypeDesc = getConsolidatedFlatType(RSRC, n1FlatTypeID, po)

    # Recognize the DCO - start with Controls which use four or more FP TypeDescs, or the amount is dynamic
    if dcoTypeDesc.get("Type") == "TypeDef" and n1TypeDesc.get("Type") == "NumUInt32":
        # Controls from Array/Matrix/Cluster category: Real Matrix, Complex Matrix
        # These use six TDs (for 2 dimensions), first and last pointing at the same flat TypeDef TD; second and third are
        # per-dimension NumUInt32 shift TDs; fourth is Array, fifth is the element type Num TD.
        match = True
        dcoInnerTypeDesc = dcoTypeDesc.find("./TypeDesc[@Type]")
        if dcoInnerTypeDesc is not None and dcoInnerTypeDesc.get("Type") == "Array":
            nDimensions = len(dcoInnerTypeDesc.findall("./Dimension"))
        else:
            nDimensions = 0
        if nDimensions < 1:
            match = False
        partTypeIDs = []
        for dimID in range(nDimensions):
            if len(flatTypeIDList) > 1+dimID:
                n2FlatTypeID = flatTypeIDList[1+dimID]
                n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
            else:
                n2TypeDesc, n2FlatTypeID = None, None
            if n2TypeDesc is not None and n2TypeDesc.get("Type") == "NumUInt32":
                partTypeIDs.append(1+dimID)
            else:
                match = False
        if len(partTypeIDs) != nDimensions:
            match = False
        dcoSubTypeDesc = dcoInnerTypeDesc.find("./TypeDesc[@TypeID]")
        if len(flatTypeIDList) > 1+nDimensions+0:
            n3FlatTypeID = flatTypeIDList[1+nDimensions+0]
            n3TypeDesc = getConsolidatedFlatType(RSRC, n3FlatTypeID, po)
        else:
            n3TypeDesc, n3FlatTypeID = None, None
        if n3TypeDesc is not None and n3TypeDesc.get("Type") == "Array":
            n3Dimensions = len(n3TypeDesc.findall("./Dimension"))
            n3SubTypeDesc = n3TypeDesc.find("./TypeDesc[@TypeID]")
        else:
            n3Dimensions = 0
            n3SubTypeDesc = None
        if nDimensions != n3Dimensions:
            match = False
        if dcoSubTypeDesc is None or n3SubTypeDesc is None or dcoSubTypeDesc.get("TypeID") != n3SubTypeDesc.get("TypeID"):
            match = False
        if len(flatTypeIDList) > 1+nDimensions+1:
            n4FlatTypeID = flatTypeIDList[1+nDimensions+1]
            n4TypeDesc = getConsolidatedFlatType(RSRC, n4FlatTypeID, po)
        else:
            n4TypeDesc, n4FlatTypeID = None, None
        if n4TypeDesc is None or n4TypeDesc.get("Type") not in ("NumUInt32","NumFloat64","NumComplex128",):
            match = False
        if len(flatTypeIDList) > 1+nDimensions+2:
            n5FlatTypeID = flatTypeIDList[1+nDimensions+2]
            n5TypeDesc = getConsolidatedFlatType(RSRC, n5FlatTypeID, po)
        else:
            n5TypeDesc, n5FlatTypeID = None, None
        if dcoFlatTypeID != n5FlatTypeID:
            match = False
        if match:
            DCOInfo = { 'fpClass': "typeDef", 'dcoTypeID': 0, 'partTypeIDs': partTypeIDs, 'ddoTypeID': 1+nDimensions+2, 'subTypeIDs': [] }
            return 1+nDimensions+3, DCOInfo
    if dcoTypeDesc.get("Type") == "UnitUInt32" and dcoTypeDesc.get("Type") == n1TypeDesc.get("Type") and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Boolean category: RabioButtons
        # These use two Unit TDs, followed by bool TD for each radio button; both Unit TDs are pointing at the same flat index of UnitUInt TD,
        # radio buttons have separate TD for each. Unit TD has as much Enum entries as there are following radio button TDs.
        dcoSubTypeEnumLabels = dcoTypeDesc.findall("./EnumLabel")
        # Following that, we expect bool types from each radio button
        subTypeIDs = []
        subFlatTypeIDs = []
        match = True
        for i, dcoSubTypeEnLabel in enumerate(dcoSubTypeEnumLabels):
            if len(flatTypeIDList) <= i:
                match = False
                break
            subFlatTypeID = flatTypeIDList[2+i]
            subTypeDesc = getConsolidatedFlatType(RSRC, subFlatTypeID, po)
            if subTypeDesc is None or subTypeDesc.get("Type") != "Boolean":
                match = False
                break
            subFlatTypeIDs.append(subFlatTypeID)
            subTypeIDs.append(2+i)
        # The Flat Types inside needs to be unique for each radio button
        if len(subFlatTypeIDs) > len(set(subFlatTypeIDs)):
            match = False # Some types repeat - fail
        if match:
            DCOInfo = { 'fpClass': "radioClust", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': subTypeIDs }
            return 2+len(dcoSubTypeEnumLabels), DCOInfo
    if dcoTypeDesc.get("Type") == "Cluster" and n1TypeDesc.get("Type") == "Cluster" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Array/Matrix/Cluster category: Cluster
        # Also matches control from Graph Datatypes category: Point, Rect, Text Alignment, User Font
        # These use two Cluster TDs of same flat index, followed by TDs for each item within the cluster, but without DCO TDs.
        # The items from inside cluster can be in different order than "master" types.
        dcoSubTypeDescMap = dcoTypeDesc.findall("./TypeDesc")
        dcoSubTypeDescList = []
        for TDTopMap in dcoSubTypeDescMap:
            TypeDesc, _, _ = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
            if TypeDesc is None: continue
            dcoSubTypeDescList.append(TypeDesc)
        # Following that, we expect types from inside the Cluster; make all are matching
        subTypeIDs = []
        match = True
        # TODO it would seem that the items may be in different order in sub-TDs than inside the main cluster; see "User Font" control for an example
        # TODO We should accept any order, as long as all types have a match.
        for i, expectSubTypeDesc in enumerate(reversed(dcoSubTypeDescList)):
            subFlatTypeID = flatTypeIDList[2+i]
            subTypeDesc = getConsolidatedFlatType(RSRC, subFlatTypeID, po)
            if expectSubTypeDesc.get("Type") != subTypeDesc.get("Type"):
                match = False
                break
            subTypeIDs.append(2+i)
        if match:
            DCOInfo = { 'fpClass': "stdClust", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': subTypeIDs }
            return 2+len(dcoSubTypeDescList), DCOInfo
    if dcoTypeDesc.get("Type") in ("Cluster","Array","NumFloat64",) and n1TypeDesc.get("Type") == "NumUInt32":
        # Controls from Graph category: Digital Waveform, Waveform Chart, Waveform Graph, XY Graph, Ex XY Graph
        # These use over fifteen TDs, first and last pointing at the same flat TD of Cluster,Array or NumFloat64 type; inbetween there is
        #   a combination of NumUInt32, Array, Cluster, String, Boolean, with some chunks of the types depending on specific control kind.
        match = True
        # Verify DCO TypeID
        if dcoTypeDesc.get("Type") == "Cluster":
            # For control: Digital Waveform
            dcoSubTypeDescMap = dcoTypeDesc.findall("./TypeDesc[@TypeID]")
            if len(dcoSubTypeDescMap) != 4:
                match = False
            # Vefify fields within Cluster
            for i, dcoSubTypeMap in enumerate(dcoSubTypeDescMap):
                dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTypeMap, po)
                if dcoSubTypeDesc is None:
                    match = False
                    break
                if i in (0,1,):
                    if dcoSubTypeDesc.get("Type") != "NumFloat64":
                        match = False
                elif i in (2,):
                    if dcoSubTypeDesc.get("Type") != "Array":
                        match = False
                elif i in (3,):
                    if dcoSubTypeDesc.get("Type") != "NumInt32":
                        match = False
                if not match:
                    break
        elif dcoTypeDesc.get("Type") == "Array":
            dcoSubTypeMap = dcoTypeDesc.find("./TypeDesc[@TypeID]")
            if dcoSubTypeMap is not None:
                dcoSubVarTypeDesc, _, dcoFlatClusterTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTypeMap, po)
            else:
                dcoSubVarTypeDesc, dcoFlatClusterTypeID = None, None
            if dcoSubVarTypeDesc is not None and dcoSubVarTypeDesc.get("Type") == "NumFloat64":
                # For control: Waveform Graph
                pass
            elif dcoSubVarTypeDesc is not None and dcoSubVarTypeDesc.get("Type") == "Cluster":
                # For controls: XY Graph (dcoSubClustTypeDesc is Cluster), Ex XY Graph (dcoSubClustTypeDesc is Array)
                dcoSubClustTypeMap = dcoSubVarTypeDesc.findall("./TypeDesc[@TypeID]")
                if len(dcoSubClustTypeMap) != 2:
                    match = False
                firstType = None
                for i, dcoSubClustTypeMap in enumerate(dcoSubClustTypeMap):
                    dcoSubClustTypeDesc, _, dcoFlatSubClustTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTypeMap, po)
                    if dcoSubClustTypeDesc.get("Type") != "Array" and dcoSubClustTypeDesc.get("Type") != "Cluster":
                        match = False
                    # All the types inside are the same
                    if firstType is None:
                        firstType = dcoSubClustTypeDesc.get("Type")
                    if dcoSubClustTypeDesc.get("Type") != firstType:
                        match = False
                    if not match:
                        break
        prop1TypeIDShift = 1
        # Verify TDs between DCO TD and DDO TD - constant part at start
        prop1TypeIDs = []
        if len(flatTypeIDList) > prop1TypeIDShift+3:
            for i in range(3):
                niFlatTypeID = flatTypeIDList[prop1TypeIDShift+i]
                niTypeDesc = getConsolidatedFlatType(RSRC, niFlatTypeID, po)
                if niTypeDesc is None:
                    break
                if   i == 0:
                    if niTypeDesc.get("Type") != "NumUInt32":
                        break
                elif i == 1:
                    if niTypeDesc.get("Type") != "Array":
                        break
                elif i == 2:
                    if niTypeDesc.get("Type") != "Cluster":
                        break
                    niPartTypeDesc = niTypeDesc.findall("./TypeDesc[@TypeID]")
                    #TODO check the Cluster content
                prop1TypeIDs.append(prop1TypeIDShift+i)
        if len(prop1TypeIDs) != 3:
            match = False
        prop2TypeIDShift = prop1TypeIDShift+len(prop1TypeIDs)
        # Verify TDs between DCO TD and DDO TD - optional middle part
        prop2TypeIDs = []
        if len(flatTypeIDList) > prop2TypeIDShift+6:
            for i in range(6):
                niFlatTypeID = flatTypeIDList[prop2TypeIDShift+i]
                niTypeDesc = getConsolidatedFlatType(RSRC, niFlatTypeID, po)
                if niTypeDesc is None:
                    break
                if   i == 0:
                    if niTypeDesc.get("Type") != "String":
                        break
                elif i in (1,2,):
                    if niTypeDesc.get("Type") != "Boolean":
                        break
                elif i == 3:
                    if niTypeDesc.get("Type") != "NumUInt32":
                        break
                elif i == 4:
                    if niTypeDesc.get("Type") != "Array":
                        break
                elif i == 5:
                    if niTypeDesc.get("Type") != "Cluster":
                        break
                    niPartTypeDesc = niTypeDesc.findall("./TypeDesc[@TypeID]")
                    #TODO check the Cluster content
                prop2TypeIDs.append(prop2TypeIDShift+i)
        # Optional part - if no match found, assume it's not there
        if len(prop2TypeIDs) != 6:
            prop2TypeIDs = [] # Continue as if nothing was matched
        prop3TypeIDShift = prop2TypeIDShift+len(prop2TypeIDs)
        # Verify TDs between DCO TD and DDO TD - constant part near end
        prop3TypeIDs = []
        if len(flatTypeIDList) > prop3TypeIDShift+10:
            for i in range(10):
                niFlatTypeID = flatTypeIDList[prop3TypeIDShift+i]
                niTypeDesc = getConsolidatedFlatType(RSRC, niFlatTypeID, po)
                if niTypeDesc is None:
                    break
                if   i == 0:
                    if niTypeDesc.get("Type") != "String":
                        break
                elif i in (1,2,3,):
                    if niTypeDesc.get("Type") != "Boolean":
                        break
                elif i == 4:
                    if niTypeDesc.get("Type") != "Cluster":
                        break
                    niPartTypeDesc = niTypeDesc.findall("./TypeDesc[@TypeID]")
                    #TODO check the Cluster content
                elif i in (5,6,7,8,):
                    if niTypeDesc.get("Type") != "Boolean":
                        break
                elif i == 9:
                    if niTypeDesc.get("Type") != "Array":
                        break
                prop3TypeIDs.append(prop3TypeIDShift+i)
        if len(prop3TypeIDs) != 10:
            match = False
        prop4TypeIDShift = prop3TypeIDShift+len(prop3TypeIDs)
        # Verify TDs between DCO TD and DDO TD - optional part at end
        prop4TypeIDs = []
        if len(flatTypeIDList) > prop4TypeIDShift+1:
            for i in range(1):
                niFlatTypeID = flatTypeIDList[prop4TypeIDShift+i]
                niTypeDesc = getConsolidatedFlatType(RSRC, niFlatTypeID, po)
                if niTypeDesc is None:
                    break
                if   i == 0: # Exists for: Digital Waveform
                    if niTypeDesc.get("Type") != "String":
                        break
                prop4TypeIDs.append(prop4TypeIDShift+i)
        # Optional part - if no match found, assume it's not there
        if len(prop4TypeIDs) != 1:
            prop4TypeIDs = [] # Continue as if nothing was matched
        ddoTypeIDShift = prop4TypeIDShift+len(prop4TypeIDs)
        # Make list of all part TypeIDs
        partTypeIDs = prop1TypeIDs + prop2TypeIDs + prop3TypeIDs + prop4TypeIDs

        # Verify DDO TD
        if len(flatTypeIDList) > ddoTypeIDShift:
            n21FlatTypeID = flatTypeIDList[ddoTypeIDShift]
            n21TypeDesc = getConsolidatedFlatType(RSRC, n21FlatTypeID, po)
        else:
            n21TypeDesc, n21FlatTypeID = None, None
        if n21TypeDesc is None or n21TypeDesc.get("Type") != dcoTypeDesc.get("Type") or dcoFlatTypeID != n21FlatTypeID:
            match = False

        subTypeIDs = []
        hasHistTD = True
        # For some controls, we have additional Cluster at end; detect it by content
        if hasHistTD:
            if len(flatTypeIDList) > ddoTypeIDShift+1:
                histFlatTypeID = flatTypeIDList[ddoTypeIDShift+1]
                histTypeDesc = getConsolidatedFlatType(RSRC, histFlatTypeID, po)
            else:
                histTypeDesc, histFlatTypeID = None, None
            if histTypeDesc is not None and histTypeDesc.get("Type") == "Cluster":
                histClustTypeMap = histTypeDesc.findall("./TypeDesc[@TypeID]")
            else:
                histClustTypeMap = []

            if len(histClustTypeMap) != 6:
                hasHistTD = False
            histClustTypeDescList = []
            histClustFlatTypeIDList = []
            for hcTypeMap in histClustTypeMap:
                hcTypeDesc, _, hcFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, hcTypeMap, po)
                if hcTypeDesc is None:
                    break
                histClustTypeDescList.append(hcTypeDesc)
                histClustFlatTypeIDList.append(hcFlatSubTypeID)
            if len(histClustTypeDescList) == 6:
                if histClustTypeDescList[0].get("Type") == "Cluster" and histClustFlatTypeIDList[0] == histClustFlatTypeIDList[5]:
                    histCCTypeMap = histClustTypeDescList[0].findall("./TypeDesc[@TypeID]")
                else:
                    histCCTypeMap = []
                if len(histCCTypeMap) != 4:
                    hasHistTD = False

                for hcci, hccTypeMap in enumerate(histCCTypeMap):
                    hccTypeDesc, _, hccFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, hccTypeMap, po)
                    if hccTypeDesc is None:
                        hasHistTD = False
                        break
                    if hcci in (0,1,2,):
                        if hccTypeDesc.get("Type") != "NumInt32":
                            hasHistTD = False
                            break
                    elif hcci == 3:
                        if hccTypeDesc.get("Type") != "Array":
                            hasHistTD = False
                            break
                        #TODO we could verify the array type
                if histClustTypeDescList[1].get("Type") != "NumInt32":
                    hasHistTD = False
                if histClustTypeDescList[2].get("Type") != "NumInt16" or histClustFlatTypeIDList[2] != histClustFlatTypeIDList[3]:
                    hasHistTD = False
                if histClustTypeDescList[4].get("Type") != "NumUInt32":
                    hasHistTD = False
            else:
                hasHistTD = False
        if hasHistTD:
            subTypeIDs.append(ddoTypeIDShift+1)
        if match:
            DCOInfo = { 'fpClass': "stdGraph", 'dcoTypeID': 0, 'partTypeIDs': partTypeIDs, 'ddoTypeID': ddoTypeIDShift, 'subTypeIDs': subTypeIDs }
            return ddoTypeIDShift+len(subTypeIDs)+1, DCOInfo
    if dcoTypeDesc.get("Type") == "UnitUInt32" and n1TypeDesc.get("Type") == "UnitUInt32" and dcoFlatTypeID != n1FlatTypeID:
        # Controls from Containers category: TabControl
        # These use four TDs, first and last pointing at the same flat TD; second has its own TD, of the same type; third is NumInt32.
        match = True
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        if n2TypeDesc is None or n2TypeDesc.get("Type") not in ("NumInt32",):
            match = False
        if len(flatTypeIDList) > 3:
            n3FlatTypeID = flatTypeIDList[3]
            n3TypeDesc = getConsolidatedFlatType(RSRC, n3FlatTypeID, po)
        else:
            n3TypeDesc, n3FlatTypeID = None, None
        if dcoFlatTypeID != n3FlatTypeID:
                match = False
        if match:
            DCOInfo = { 'fpClass': "tabControl", 'dcoTypeID': 0, 'partTypeIDs': [ 1, 2 ], 'ddoTypeID': 3, 'subTypeIDs': [] }
            return 4, DCOInfo

    # Controls which use three or less FP TypeDefs are left below
    if dcoTypeDesc.get("Type") == "Array" and n1TypeDesc.get("Type") == "Array" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from 3D Graph category: Bar, Comet, Contour, LineGraph, Mesh, ParametricGraph, Pie, Quiver, Ribbon,
        #   Scatter, Stem, Surface, SurfaceGraph, Waterfall
        # Controls from Graph category: Error Bar Plot, Feather Plot, XY Plot Matrix
        # These use three TDs; two are pointing at the same flat index of Array TD; third is a TypeDef with Cluster TD for state.
        match = True
        # Get the array item type
        dcoSubTDMap = dcoTypeDesc.find("./TypeDesc[@TypeID]")
        dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, dcoSubTDMap, po)
        # Ref type is UDClassInst
        if dcoSubTypeDesc.get("Type") != "Refnum" or dcoSubTypeDesc.get("RefType") not in ("UDClassInst",):
            match = False
        # Now check the third TD
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        if n2TypeDesc is not None and n2TypeDesc.get("Type") == "TypeDef":
            n2ClustTypeDesc = n2TypeDesc.find("./TypeDesc[@Type]")
        else:
            n2ClustTypeDesc = None
        if n2ClustTypeDesc is not None and n2ClustTypeDesc.get("Type") == "Cluster":
            n2SubTypeDesc = n2ClustTypeDesc.findall("./TypeDesc[@TypeID]")
        else:
            n2SubTypeDesc = []
        # The state Cluster has 3 or more items; first is a copy of DCO sub-TD, second is TypeDef with queue, following are some int properties.
        if len(n2SubTypeDesc) < 3 or len(n2SubTypeDesc) > 9:
            match = False
        expectContent = ""
        for i, stateTypeMap in enumerate(n2SubTypeDesc):
            stateTypeDesc, _, stateFlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, stateTypeMap, po)
            if stateTypeDesc is None:
                match = False
                break
            if i == 0:
                if stateTypeDesc.get("Type") == "TypeDef":
                    expectContent = "LineGraph"
                elif stateTypeDesc.get("Type") == dcoSubTypeDesc.get("Type"):
                    expectContent = "Contour"
                else:
                    match = False
                    break
            if   expectContent == "LineGraph":
                if i == 0: # Graph Properties
                    if stateTypeDesc.get("Type") != "TypeDef":
                        match = False
                    grpropTypeDesc = stateTypeDesc.find("./TypeDesc[@Type]")
                    if grpropTypeDesc is not None and grpropTypeDesc.get("Type") == "Cluster":
                        grpropTypeMapList = grpropTypeDesc.findall("./TypeDesc[@TypeID]")
                    else:
                        grpropTypeMapList = []
                    if len(grpropTypeMapList) != 9:
                        match = False
                elif i == 1: # Plot/Axes/Cursor Properties
                    if stateTypeDesc.get("Type") != "TypeDef":
                        match = False
                    pacpropTypeDesc = stateTypeDesc.find("./TypeDesc[@Type]")
                    if pacpropTypeDesc is not None and pacpropTypeDesc.get("Type") == "Cluster":
                        pacpropTypeMapList = pacpropTypeDesc.findall("./TypeDesc[@TypeID]")
                    else:
                        pacpropTypeMapList = []
                    if len(grpropTypeMapList) != 9:
                        match = False
                    for ppi, pacpropTypeMap in enumerate(pacpropTypeMapList):
                        ppeTypeDesc, _, ppeFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, pacpropTypeMap, po)
                        if ppi in (1,2,3,4,5,6,):
                            if stateTypeDesc.get("Type") != "TypeDef":
                                match = False
                            #TODO we could check content of each typedef
                        elif ppi == 7:
                            if stateTypeDesc.get("Type") != "Array":
                                match = False
                            #TODO we could check content of that array
                elif i in (2,3,4,):
                    if stateTypeDesc.get("Type") != "NumInt32":
                        match = False
                else:
                    if stateTypeDesc.get("Type") != "Boolean":
                        match = False
            elif expectContent == "Contour":
                if i == 0:
                    if stateTypeDesc.get("Type") != dcoSubTypeDesc.get("Type") or stateTypeDesc.get("RefType") != dcoSubTypeDesc.get("RefType"):
                        match = False
                elif i == 1:
                    if stateTypeDesc.get("Type") != "TypeDef":
                        match = False
                    stateRefTypeDesc = stateTypeDesc.find("./TypeDesc[@Type]")
                    if stateRefTypeDesc is not None and stateRefTypeDesc.get("Type") == "Refnum" and stateRefTypeDesc.get("RefType") == "Queue":
                        queueTypeMap = stateRefTypeDesc.find("./TypeDesc[@TypeID]")
                    else:
                        queueTypeMap = None
                    if queueTypeMap is not None:
                        queueTypeDesc, _, queueFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, queueTypeMap, po)
                    else:
                        queueTypeDesc, queueFlatSubTypeID = None, None
                    if queueTypeDesc is None or queueTypeDesc.get("Type") != "TypeDef":
                        match = False
                else:
                    if stateTypeDesc.get("Type") != "NumUInt32":
                        match = False
        if match:
            DCOInfo = { 'fpClass': "xControl", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': [ 2 ] }
            return 3, DCOInfo
    if dcoTypeDesc.get("Type").startswith("Num") and dcoTypeDesc.get("Type") == n1TypeDesc.get("Type") and dcoFlatTypeID != n1FlatTypeID:
        # Controls from Numeric category: Dial, Gauge, Knob, Meter
        # We will also use it instead of "stdSlide", as there is no way to distinguish these
        # These use three TDs, first and last pointing at the same flat TD; second has its own TD, of the same type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            DCOInfo = { 'fpClass': "stdKnob", 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    if dcoTypeDesc.get("Type") == "MeasureData" and dcoTypeDesc.get("Flavor") == "TimeStamp" and n1TypeDesc.get("Type") == "Boolean" and dcoFlatTypeID != n1FlatTypeID:
        # Controls from Numeric category: Timestamp Control, Timestamp Indicator
        # These use three TDs, first and last pointing at the same flat Measuredata TD; second has its own TD, of Boolean type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            DCOInfo = { 'fpClass': "absTime", 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo
    if dcoTypeDesc.get("Type") == "Array" and n1TypeDesc.get("Type") == "NumUInt32" and dcoFlatTypeID != n1FlatTypeID:
        # Controls from Array/Matrix/Cluster category: Array
        # These use three TDs, first and last pointing at the same flat Array TD; second has its own TD, of NumUInt32 type.
        if len(flatTypeIDList) > 2:
            n2FlatTypeID = flatTypeIDList[2]
            n2TypeDesc = getConsolidatedFlatType(RSRC, n2FlatTypeID, po)
        else:
            n2TypeDesc, n2FlatTypeID = None, None
        match = True
        if dcoFlatTypeID != n2FlatTypeID:
                match = False
        if match:
            DCOInfo = { 'fpClass': "indArr", 'dcoTypeID': 0, 'partTypeIDs': [ 1 ], 'ddoTypeID': 2, 'subTypeIDs': [] }
            return 3, DCOInfo

    # Controls which use two or less FP TypeDefs are left below
    if dcoTypeDesc.get("Type") == "Boolean" and n1TypeDesc.get("Type") == "Boolean" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Boolean category: Buttons, Switches and LEDs
        # These use two TDs, both pointing at the same flat index of Boolean TD.
        if True:
            DCOInfo = { 'fpClass': "stdBool", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    if dcoTypeDesc.get("Type").startswith("Num") and n1TypeDesc.get("Type").startswith("Num") and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Numeric category: Numeric Control, Numeric Indicator
        # We will also use it instead of "stdColorNum" and "scrollbar", as there is no way to distinguish these
        # These use two TDs, both pointing at the same flat Number TD.
        if True:
            DCOInfo = { 'fpClass': "stdNum", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    if dcoTypeDesc.get("Type") == "String" and n1TypeDesc.get("Type") == "String" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from String and Path category: String Control, String Indicator
        # These use two TDs, both pointing at the same flat index of String TD.
        if True:
            DCOInfo = { 'fpClass': "stdString", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    if dcoTypeDesc.get("Type") == "Picture" and n1TypeDesc.get("Type") == "Picture" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Graph category: 2D Picture, Distribution Plot, Min Max Plot, Polar Plot, Radar Plot, Smith Plot
        # These use two TDs, both pointing at the same flat index of Picture TD.
        if True:
            DCOInfo = { 'fpClass': "stdPict", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    if dcoTypeDesc.get("Type") == "UnitUInt16" and dcoTypeDesc.get("Type") == n1TypeDesc.get("Type") and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Graph DataType category: Font Enum
        # These use two Unit TDs; both Unit TDs are pointing at the same flat index of UnitUInt TD,
        if True:
            DCOInfo = { 'fpClass': "stdRing", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    if dcoTypeDesc.get("Type") == "Refnum" and n1TypeDesc.get("Type") == "Refnum" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from Containers category: ActiveX Container, dotNET Container
        # Also matches controls from dotNet and ActiveX category - specific control should be recognized later.
        # These use two TDs, both pointing at the same flat index of Refnum TD.
        # Existence of Containers in the VI can be determined by existence of VINS block with multiple entries.
        match = True
        # Ref type is AutoRef for ActiveX Container, DotNet for dotNET Container
        if dcoTypeDesc.get("RefType") not in ("AutoRef","DotNet",):
            match = False
        if match:
            DCOInfo = { 'fpClass': "stdCont", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    if dcoTypeDesc.get("Type") == "Refnum" and n1TypeDesc.get("Type") == "Refnum" and dcoFlatTypeID == n1FlatTypeID:
        # Controls from 3D Graph category: 3D Picture
        # These use two TDs, both pointing at the same flat index of Refnum TD.
        match = True
        if dcoTypeDesc.get("RefType") != "LVObjCtl":
            match = False
        if match:
            DCOInfo = { 'fpClass': "scenegraphdisplay", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 1, 'subTypeIDs': [] }
            return 2, DCOInfo
    if dcoTypeDesc.get("Type") == "Refnum":
        # Controls from Containers category, FP parts: Sub Panel
        # These use one FP TD, of Refnum type.
        # These controls have FP TypeIDs and BD TypeIDs - this will match the FP part only.
        # We're using only one TD entry here, but we've requested 2 - that's not an issue, since this DCO enforces a lot of following BD heap TDs
        match = True
        if dcoTypeDesc.get("RefType") not in ("LVObjCtl",):
            match = False
        if match:
            DCOInfo = { 'fpClass': "grouper", 'dcoTypeID': 0, 'partTypeIDs': [], 'ddoTypeID': 0, 'subTypeIDs': [] }
            return 1, DCOInfo

    #TODO recognize BD part of Sub Panel (maybe separate function for BD recognition?)
    #TODO recognize splitter - not from TDs, but it should be recognizable.
    # No control recognized
    return 0, None


def DTHP_TypeDesc_matching_ranges(RSRC, fo, po, VCTP_TypeDescList=None, VCTP_FlatTypeDescList=None):
    """ Finds possible ranges of TypeDescs for DTHP
    """
    # DTHP must not include TypeDesc values used by other sections
    heapRanges = TypeDesc_find_unused_ranges(RSRC, fo, po, skipRm=["TM80","DTHP"], \
          VCTP_TypeDescList=VCTP_TypeDescList, VCTP_FlatTypeDescList=VCTP_TypeDescList)
    if True:
        # We need TM80 to convert TMIs into TypeIDs
        TM80_IndexShift = None
        TM80 = RSRC.find("./TM80/Section")
        if TM80 is not None:
            TM80_IndexShift = TM80.get("IndexShift")
            if TM80_IndexShift is not None:
                TM80_IndexShift = int(TM80_IndexShift, 0)
    if True:
        # DTHP range is always above TM80 IndexShift
        # This is not directly enforced in code, but before Heap TypeDescs
        # there are always TypeDescs which store options, and those are
        # filled with DFDS, meaning they have to be included in TM80 range
        heapRanges = intRangesExcludeBelow(heapRanges, TM80_IndexShift)
        if (po.verbose > 2):
            print("{:s}: After TM80 IndexShift exclusion, heap TD ranges: {}"\
                .format(po.xml,heapRanges))
    if True:
        # DTHP IndexShift must be high enough to not include TypeDesc from CONP
        # Since CONP type is created with new VIs it is always before any heap TDs
        # The same does not apply to CPC2 - that type is created when first connector
        # from pane is assigned; so it's sometimes placed before, sometimes after heap TDs
        CONP_TypeID = None
        CONP_TypeDesc = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDesc is not None:
            CONP_TypeID = CONP_TypeDesc.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
        heapRanges = intRangesExcludeBelow(heapRanges, CONP_TypeID)
        if (po.verbose > 2):
            print("{:s}: After CONP exclusion, heap TD ranges: {}"\
                .format(po.xml,heapRanges))
    if True:
        # DTHP must not include TypeDesc of type "Function"
        # IndexShift must be high enough or count must be small enough to keep
        # Function TDs outside.
        nonHeapTypes = []
        for TDTopMap in VCTP_TypeDescList:
            TypeDesc, TDTopMap_Index, FlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
            if TypeDesc is None: continue
            if TypeDesc.get("Type") == "Function":
                # Function type can only be part of heap types if its FlatTypeID is used two times
                # in the file, and the other use is not a heap type.
                for otherTDTopMap in VCTP_TypeDescList:
                    otherTypeDesc, otherTDTopMap_Index, otherFlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, otherTDTopMap, po)
                    # Let's assume the second use of the same Function type can be in heap types
                    # So only if we are on first use of that flat type, disallow it s use in heap
                    if otherFlatTypeID == FlatTypeID:
                        if otherTDTopMap_Index == TDTopMap_Index:
                            nonHeapTypes.append(TDTopMap_Index)
                        break
            #TODO check if other types should be removed from heap
        for TypeDesc_Index in nonHeapTypes:
            heapRanges = intRangesExcludeOne(heapRanges, TypeDesc_Index)
        if (po.verbose > 2):
            print("{:s}: After Type based exclusion, heap TD ranges: {}"\
                .format(po.xml,heapRanges))
    # DTHP must match the two-per-TD layout (with proper exceptions)
    # Valid ranges contain ref to the same type twice for each DCO, single types are only used after Cluster
    # (and they must match the fields within cluster)
    heapRangesProper = []
    for rng in heapRanges:
        properMin = None
        properMax = None
        typeID = rng.min
        # Recognize one DCO for each move through this loop (proper DCO requires two or more typeID values; so increment varies)
        while typeID < rng.max: # rng.max is a proper value, but can't be start of DCO - at least two types make a DCO
            tdCount, DCOInfo = DCO_recognize_from_typeIDs(RSRC, fo, po, typeID, rng.max, VCTP_TypeDescList, VCTP_FlatTypeDescList)
            if DCOInfo is not None:
                # Got a proper types list for DCO
                if properMin is None:
                    properMin = typeID
                properMax = typeID + tdCount - 1 # Max value in our ranges is the last included index
                typeID += tdCount
            else:
                # No control recognized - store the previous range and search for next valid range
                if (po.verbose > 2):
                    print("{:s}: TypeID {} not viable for heap after checking subsequent types"\
                      .format(po.xml,typeID))
                if properMax is not None:
                    rng = SimpleNamespace(min=properMin,max=properMax)
                    heapRangesProper.append(rng)
                properMin = None
                properMax = None
                typeID += 1
        # Store the last proper range, in case loop ended before it had the chance of being saved
        if properMax is not None:
            rng = SimpleNamespace(min=properMin,max=properMax)
            heapRangesProper.append(rng)
    heapRanges = heapRangesProper
    return heapRanges

def DTHP_Fix(RSRC, DTHP, ver, fo, po):
    typeDescSlice = DTHP.find("./TypeDescSlice")
    if typeDescSlice is None:
        typeDescSlice = ET.SubElement(DTHP, "TypeDescSlice")
        fo[FUNC_OPTS.changed] = True
    indexShift = typeDescSlice.get("IndexShift")
    if indexShift is not None:
        indexShift = int(indexShift, 0)
    tdCount = typeDescSlice.get("Count")
    if tdCount is not None:
        tdCount = int(tdCount, 0)
    # We have current values, now compute proper ones
    VCTP = RSRC.find("./VCTP/Section")
    VCTP_TypeDescList = []
    VCTP_FlatTypeDescList = None
    if VCTP is not None:
        VCTP_TypeDescList = VCTP.findall("TopLevel/TypeDesc")
        VCTP_FlatTypeDescList = VCTP.findall("TypeDesc")
    heapRanges = DTHP_TypeDesc_matching_ranges(RSRC, fo, po, \
          VCTP_TypeDescList=VCTP_TypeDescList, \
          VCTP_FlatTypeDescList=VCTP_FlatTypeDescList)
    dcoDataTypes = getDCOMappingForIntField(RSRC, 'defaultDataTMI', po)
    minIndexShift = 0
    maxTdCount = 0
    if (po.verbose > 1):
        print("{:s}: Possible heap TD ranges: {}"\
            .format(po.xml,heapRanges))
    for rng in heapRanges:
        if rng.max - rng.min + 1 <= maxTdCount:
            continue
        minIndexShift = rng.min
        maxTdCount = rng.max - rng.min + 1
    if maxTdCount <= 0 and len(dcoDataTypes) > 0:
        # if range is empty but we have dcoDataTypes, then we can create new types for DTHP
        if (po.verbose > 1):
            print("{:s}: No TypeDesc entries found for DTHP; need to re-create the entries"\
                .format(po.xml))
        minIndexShift = getMaxIndexFromList(VCTP_TypeDescList, fo, po) + 1
        maxIndexShift = minIndexShift
        # Flat types is dcoDataTypes should be used to re-create VCTP entries needed for DTHP
        VCTP_TopLevel = VCTP.find("TopLevel")
        for dcoIndex, dcoTypeID in reversed(dcoDataTypes.items()):
            dcoTypeDesc, dcoFlatTypeID = \
                  getTypeDescFromIDUsingLists(VCTP_TypeDescList, VCTP_FlatTypeDescList, dcoTypeID, po)
            if (po.verbose > 1):
                print("{:s}: Re-creating DTHP entries for DCO{} using FlatTypeID {}"\
                    .format(po.xml,dcoIndex,dcoFlatTypeID))
            # DCO TypeDesc
            elem = ET.Element("TypeDesc")
            elem.set("Index", str(maxIndexShift))
            elem.set("FlatTypeID", str(dcoFlatTypeID))
            VCTP_TopLevel.append(elem)
            maxIndexShift += 1
            # DDO TypeDesc
            elem = ET.Element("TypeDesc")
            elem.set("Index", str(maxIndexShift))
            elem.set("FlatTypeID", str(dcoFlatTypeID))
            VCTP_TopLevel.append(elem)
            maxIndexShift += 1
            # Sub-types
            if dcoTypeDesc.get("Type") == "Cluster":
                dcoSubTypeDescMap = list(filter(lambda f: f.tag is not ET.Comment, dcoTypeDesc.findall("./TypeDesc")))
                for TDTopMap in reversed(dcoSubTypeDescMap):
                    dcoSubTypeDesc, _, dcoFlatSubTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
                    elem = ET.Element("TypeDesc")
                    elem.set("Index", str(maxIndexShift))
                    elem.set("FlatTypeID", str(dcoFlatSubTypeID))
                    VCTP_TopLevel.append(elem)
                    maxIndexShift += 1
        maxTdCount = maxIndexShift - minIndexShift
    elif maxTdCount <= 0:
        if (po.verbose > 1):
            print("{:s}: No TypeDesc entries found for DTHP, and no DCO TDs to re-create them"\
                .format(po.xml))
        pass
    if indexShift is None or indexShift < minIndexShift:
        if (po.verbose > 0):
            print("{:s}: Changing 'DTHP/TypeDescSlice' IndexShift to {}"\
                .format(po.xml,minIndexShift))
        indexShift = minIndexShift
        typeDescSlice.set("IndexShift","{}".format(indexShift))
        fo[FUNC_OPTS.changed] = True
    if tdCount is None or tdCount > maxTdCount:
        if (po.verbose > 0):
            print("{:s}: Changing 'DTHP/TypeDescSlice' Count to {}"\
                .format(po.xml,maxTdCount))
        tdCount = maxTdCount
        typeDescSlice.set("Count","{}".format(tdCount))
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def DFDS_Fix(RSRC, DFDS, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def BDPW_Fix(RSRC, BDPW, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def LVSR_Fix(RSRC, LVSR, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def VCTP_Fix(RSRC, VCTP, ver, fo, po):
    return fo[FUNC_OPTS.changed]

def CONP_Fix(RSRC, CONP, ver, fo, po):
    #TODO CONP can be re-created from DSInit
    return fo[FUNC_OPTS.changed]

def CPC2_TypeDesc_matching_ranges(RSRC, fo, po, VCTP_TypeDescList=None, VCTP_FlatTypeDescList=None):
    """ Finds possible ranges of TypeDesc for CPC2
    """
    # DTHP must not include TypeDesc values used by other sections
    conpc2Ranges = TypeDesc_find_unused_ranges(RSRC, fo, po, skipRm=["TM80","CPC2"], \
          VCTP_TypeDescList=VCTP_TypeDescList, VCTP_FlatTypeDescList=VCTP_TypeDescList)
    if True:
        # CPC2 TypeDesc type is "Function"
        nonFuncTypes = []
        for TDTopMap in VCTP_TypeDescList:
            TypeDesc, TDTopMap_Index, FlatTypeID = getTypeDescFromMapUsingList(VCTP_FlatTypeDescList, TDTopMap, po)
            if TypeDesc is None: continue
            if TypeDesc.get("Type") != "Function":
                nonFuncTypes.append(TDTopMap_Index)
        for TypeDesc_Index in nonFuncTypes:
            conpc2Ranges = intRangesExcludeOne(conpc2Ranges, TypeDesc_Index)
        if (po.verbose > 2):
            print("{:s}: After Type based exclusion, CPC2 TD ranges: {}"\
                .format(po.xml,conpc2Ranges))
    return conpc2Ranges

def CPC2_Fix(RSRC, CPC2, ver, fo, po):
    typeDescMap = CPC2.find("./TypeDesc")
    if typeDescMap is None:
        typeDescMap = ET.SubElement(CPC2, "TypeDesc")
        fo[FUNC_OPTS.changed] = True
    CPC2_typeID = typeDescMap.get("TypeID")
    if CPC2_typeID is not None:
        CPC2_typeID = int(CPC2_typeID, 0)
    # We have current value, now compute proper one
    VCTP = RSRC.find("./VCTP/Section")
    VCTP_TypeDescList = []
    VCTP_FlatTypeDescList = None
    if VCTP is not None:
        VCTP_TypeDescList = VCTP.findall("./TopLevel/TypeDesc")
        VCTP_FlatTypeDescList = VCTP.findall("./TypeDesc")
    conpc2Ranges = CPC2_TypeDesc_matching_ranges(RSRC, fo, po, \
          VCTP_TypeDescList=VCTP_TypeDescList, \
          VCTP_FlatTypeDescList=VCTP_FlatTypeDescList)
    if (po.verbose > 1):
        print("{:s}: Possible CPC2 TD ranges: {}"\
            .format(po.xml,conpc2Ranges))
    proper_typeID = None
    # Check if current value is within the vaid range
    if CPC2_typeID is not None:
        for rng in conpc2Ranges:
            if rng.min >= CPC2_typeID and rng.max <= CPC2_typeID:
                proper_typeID = CPC2_typeID
                break
    # If it's not, use the last matching type
    if proper_typeID is None and len(conpc2Ranges) > 0:
        rng = conpc2Ranges[-1]
        proper_typeID = rng.max
    # If no valid TDs in our ranges, re-create the TypeDesc
    if proper_typeID is None:
        # if range is empty but we have connector list, make the new TypeDesc based on that
        if (po.verbose > 1):
            print("{:s}: No TypeDesc entry found for CPC2; need to re-create from connectors list"\
                .format(po.xml))
        CONP_TypeDesc = None
        CONP_TypeDescMap = RSRC.find("./CONP/Section/TypeDesc")
        if CONP_TypeDescMap is not None:
            CONP_TypeID = CONP_TypeDescMap.get("TypeID")
            if CONP_TypeID is not None:
                CONP_TypeID = int(CONP_TypeID, 0)
            if CONP_TypeID is not None:
                CONP_TypeDesc = getConsolidatedTopType(RSRC, CONP_TypeID, po)
        if CONP_TypeDesc is not None:
            CONP_TDMapList = CONP_TypeDesc.findall("./TypeDesc")
        else:
            # At this point, CONP should have been re-created already
            if (po.verbose > 1):
                print("{:s}: CONP TypeDesc not found, creating empty list of connectors"\
                    .format(po.xml))
            CONP_TDMapList = []
        # Create the flat type for CPC2
        TypeDesc_elem = ET.Element("TypeDesc")
        TypeDesc_elem.set("Type","Function")
        TypeDesc_elem.set("FuncFlags","0x0")
        CONP_TypeDesc_Pattern = None
        CONP_TypeDesc_HasThrall = None
        if CONP_TypeDescMap is not None:
            CONP_TypeDesc_Pattern = CONP_TypeDescMap.get("Pattern")
            CONP_TypeDesc_HasThrall = CONP_TypeDescMap.get("HasThrall")
        if CONP_TypeDesc_Pattern is None:
            CONP_TypeDesc_Pattern = "0x8"
        if CONP_TypeDesc_HasThrall is None:
            CONP_TypeDesc_HasThrall = "0"
        TypeDesc_elem.set("Pattern", CONP_TypeDesc_Pattern)
        TypeDesc_elem.set("HasThrall",CONP_TypeDesc_HasThrall)
        TypeDesc_elem.set("Format","inline")
        # flatTypeID and flatPos will usually be the same, but just in case there's
        # a mess in tags within VCTP, let's treat them as separate values
        proper_flatTypeID = len(VCTP_FlatTypeDescList)
        proper_flatPos = list(VCTP).index(VCTP_FlatTypeDescList[-1]) + 1
        VCTP.insert(proper_flatPos,TypeDesc_elem)
        fo[FUNC_OPTS.changed] = True
        for TDFlatMap in CONP_TDMapList:
            FlatTypeID = TDFlatMap.get("TypeID") # For map entries within Function TD
            assert(FlatTypeID is not None) # this should've been re-created with CONP
            FlatTypeID = int(FlatTypeID, 0)
            FlatTDFlags = TDFlatMap.get("Flags") # For map entries within Function TD
            assert(FlatTDFlags is not None) # this should've been re-created with CONP
            FlatTDFlags = int(FlatTDFlags, 0)
            elem = ET.SubElement(TypeDesc_elem, "TypeDesc")
            elem.set("TypeID","{:d}".format(FlatTypeID))
            elem.set("Flags","0x{:04x}".format(FlatTDFlags & ~0x0401)) # checked on one example only
        # Now add a top type which references our new flat type
        VCTP_TopLevel = VCTP.find("./TopLevel")
        proper_typeID = getMaxIndexFromList(VCTP_TypeDescList, fo, po) + 1
        elem = ET.SubElement(VCTP_TopLevel, "TypeDesc")
        elem.set("Index","{:d}".format(proper_typeID))
        elem.set("FlatTypeID","{:d}".format(proper_flatTypeID))
    if CPC2_typeID != proper_typeID:
        if (po.verbose > 0):
            print("{:s}: Changing 'CPC2/TypeDesc' TypeID to {}"\
                .format(po.xml,proper_typeID))
        typeDescMap.set("TypeID","{}".format(proper_typeID))
        fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]

def BDHb_Fix(RSRC, BDHP, ver, fo, po):
    block_name = "BDHb"

    attribGetOrSetDefault(BDHP, "Index", 0, fo, po)
    sect_format = BDHP.get("Format")
    if sect_format not in ("xml",):
        BDHP.set("Format","xml")
        if len(RSRC.findall("./"+block_name+"/Section")) <= 1:
            snum_str = ""
        else:
            if sect_index >= 0:
                snum_str = str(sect_index)
            else:
                snum_str = 'm' + str(-sect_index)
        fname_base = "{:s}_{:s}{:s}".format(po.filebase, block_name, snum_str)
        BDHP.set("File","{:s}.xml".format(fname_base))
        fo[FUNC_OPTS.changed] = True

    rootObject = elemFindOrCreate(BDHP, "SL__rootObject", fo, po)
    attribGetOrSetDefault(rootObject, "class", "oHExt", fo, po)
    attribGetOrSetDefault(rootObject, "uid", 1, fo, po)

    root = elemFindOrCreate(rootObject, "root", fo, po)
    attribGetOrSetDefault(root, "class", "diag", fo, po)
    attribGetOrSetDefault(root, "uid", 1, fo, po)

    pBounds = elemFindOrCreate(rootObject, "pBounds", fo, po)
    elemTextGetOrSetDefault(pBounds, [46,0,681,1093], fo, po)
    dBounds = elemFindOrCreate(rootObject, "dBounds", fo, po)
    elemTextGetOrSetDefault(dBounds, [0,0,0,0], fo, po)

    origin = elemFindOrCreate(rootObject, "origin", fo, po)
    elemTextGetOrSetDefault(origin, [327,105], fo, po)

    instrStyle = elemFindOrCreate(rootObject, "instrStyle", fo, po)
    elemTextGetOrSetDefault(instrStyle, 31, fo, po)

    # Now content of the 'root' element

    root_zPlaneList, root_nodeList_termList, root_signalList = elemCheckOrCreate_bdroot_content( \
          root, fo, po, aeObjFlags=16384, hasPlanes=True, hasNodes=True, hasSignals=True, \
          aeBgColor=0x00FFFFFF, aeFirstNodeIdx=1, \
          aeBounds=[0,0,0,0], aeShortCount=1, aeClumpNum=0x020003)

    return fo[FUNC_OPTS.changed]


def icl8_genDefaultIcon(title, po):
    """ Generates default icon image for VI file
    """
    imageHex = \
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" +\
    "ff000000000000000000000000000000000000000000000000000000000000ff" +\
    "ff000000000000000000000000000000000000000000000000000000000000ff" +\
    "ff0000ffffffffffffffffffffffffffffffffffffff000000000000000000ff" +\
    "ff0000fffafafafafafafafafafafafaf8fa2cfa2cff000000000000000000ff" +\
    "ff0000fffafffffffffffffffffffffff8fa2cfa2cff000000000000000000ff" +\
    "ff0000fffaffd1c5d1ffffffd1c5d1fff8fc2bfc2cff000000000000000000ff" +\
    "ff0000fffaffc5ffc5ffffffc5ffc5fff82c2c2c2cff000000000000000000ff" +\
    "ff0000fffad1c5ffc5d1ffd1c5ffc5d1f82bfc2b2cff000000000000000000ff" +\
    "ff0000fffac5d1ffd1c5ffc5d1ffd1c5f8fc08fc2cff000000000000000000ff" +\
    "ff0000fffac5ffffffc5ffc5ffffffc5f8fc08fc2cff000000000000000000ff" +\
    "ff0000fffaffffffffd1c5d1fffffffff82bfc2b2cff000000000000000000ff" +\
    "ff0000fffafffffffffffffffffffffff82c2c2c2cff000000000000000000ff" +\
    "ff0000fff8f8f8f8f8f8f8f8f8f8f8f8f82c2c8383ff000000000000000000ff" +\
    "ff0000ff2c2c2c2c2c2c2c2c2c2c2c2c2c2c2c830583830000000000000000ff" +\
    "ff0000ff2cfc2c2c2c2c2cfc2c2c2c2c232323830505058383000000000000ff" +\
    "ff0000fffcd5fc2c2c2cfc23fc2c23232c2c2c830505ff0505838300000000ff" +\
    "ff0000ff2cd42c2c2c2c232c2c232c2c2c2c2c8305ffffff05050583232300ff" +\
    "ff0000ffffd5ffffff23ffff23ffffffffffff830505ff0505838300000000ff" +\
    "ff00000000d4000000230000230000d5d4d4d5830505058383000000000000ff" +\
    "ff0000000000d500000023230000d400000000830583830000000000000000ff" +\
    "ff000000000000d4d400000000d50000000000838300000000000000000000ff" +\
    "ff0000000000000000d5d4d5d4000000000000000000000000000000000000ff" +\
    "ff000000000000000000000000000000000000000000000000000000000000ff"*8 +\
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    from PIL import ImageFont, ImageDraw
    image = Image.new("P", (32, 32))
    if True:
        from LVmisc import LABVIEW_COLOR_PALETTE_256
        img_palette = [ 0 ] * (3*256)
        lv_color_palette = LABVIEW_COLOR_PALETTE_256
        for i, rgb in enumerate(lv_color_palette):
            img_palette[3*i+0] = (rgb >> 16) & 0xFF
            img_palette[3*i+1] = (rgb >>  8) & 0xFF
            img_palette[3*i+2] = (rgb >>  0) & 0xFF
        image.putpalette(img_palette, rawmode='RGB')
    img_data = bytes.fromhex(imageHex)
    image.putdata(img_data)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load("./assets/tom-thumb.pil")
    short_title = title
    if len(short_title) > 7:
        short_title = re.sub('[^A-Za-z0-9{}=-]', '', short_title)[:7]
    draw.text((2,24), short_title, font=font, fill=(0xff))
    return image

def icon_changePalette(RSRC, src_image, bpp, fo, po):
    from LVmisc import LABVIEW_COLOR_PALETTE_256, LABVIEW_COLOR_PALETTE_16, LABVIEW_COLOR_PALETTE_2
    img_palette = [ 0 ] * (3*(2**bpp))
    if bpp == 8:
        lv_color_palette = LABVIEW_COLOR_PALETTE_256
    elif bpp == 4:
        lv_color_palette = LABVIEW_COLOR_PALETTE_16
    else:
        lv_color_palette = LABVIEW_COLOR_PALETTE_2
    for i, rgb in enumerate(lv_color_palette):
        img_palette[3*i+0] = (rgb >> 16) & 0xFF
        img_palette[3*i+1] = (rgb >>  8) & 0xFF
        img_palette[3*i+2] = (rgb >>  0) & 0xFF
    palimage = Image.new('P', (2, 2))
    palimage.putpalette(img_palette, rawmode='RGB')
    rgb_image = src_image.convert('RGB')
    dst_image = rgb_image.quantize(colors=len(lv_color_palette), palette=palimage)
    return dst_image

def icon_readImage(RSRC, icon_elem, fo, po):
    """ Reads icon image from section
    """
    icon_Format = icon_elem.get("Format")
    icon_File = icon_elem.get("File")
    xml_path = os.path.dirname(po.xml)
    icon_fname = None
    if icon_File is not None:
        if len(xml_path) > 0:
            icon_fname = xml_path + '/' + icon_File
        else:
            icon_fname = icon_File
    image = None
    fileOk = (icon_fname is not None) and os.access(icon_fname, os.R_OK)
    if icon_Format == "png" and fileOk:
        # As long as the file loads, we're good
        try:
            image = Image.open(icon_fname)
            image.getdata() # to make sure the file gets loaded; everything is lazy nowadays
        except:
            fileOk = False
            image = None
    return image, icon_fname, fileOk

def icl8_Fix(RSRC, icl8, ver, fo, po):
    icl8_Format = icl8.get("Format")
    icl8_File = icl8.get("File")
    image, icl8_fname, fileOk = icon_readImage(RSRC, icl8, fo, po)
    if image is not None and fileOk:
        # If we were abe to read the image, section is OK
        return fo[FUNC_OPTS.changed]
    if icl8_Format == "bin" and fileOk:
        # Just accept that; no real need to verify BIN file
        return fo[FUNC_OPTS.changed]
    # So the section is bad; we will re-create the icon
    icl8_Format = "png"
    icl8_baseName = os.path.splitext(os.path.basename(po.xml))[0]
    icl8_File = icl8_baseName+"_icl8.png"
    if True:
        xml_path = os.path.dirname(po.xml)
        if len(xml_path) > 0:
            icl8_fname = xml_path + '/' + icl8_File
        else:
            icl8_fname = icl8_File
    if image is None:
        icl4 = RSRC.find("./icl4/Section")
        if icl4 is not None:
            image, icl4_fname, fileOk = icon_readImage(RSRC, icl4, fo, po)
        if image is not None:
            image = icon_changePalette(RSRC, image, 8, fo, po)
    if image is None:
        ICON = RSRC.find("./ICON/Section")
        if ICON is not None:
            image, ICON_fname, fileOk = icon_readImage(RSRC, ICON, fo, po)
        if image is not None:
            image = icon_changePalette(RSRC, image, 8, fo, po)
    if image is None:
        image = icl8_genDefaultIcon(icl8_baseName, po)
    image.save(icl8_fname, format="PNG")
    icl8.set("Format", icl8_Format)
    icl8.set("File", icl8_File)
    fo[FUNC_OPTS.changed] = True
    return fo[FUNC_OPTS.changed]


LVSR_SectionDef = [
 ["LVIN",	1,0,0,	None], # not sure how old it is
 ["LVSR",	5,0,0,	LVSR_Fix], # verified for LV6.0 - LV14.0
]

vers_SectionDef = [
 ["vers",	1,0,0,	vers_Fix], # no idea about versions; this one is for LV8.6 - LV14.0
]

VCTP_SectionDef = [
 ["VCTP",	7,0,0,	VCTP_Fix], # does not exist for LV6.0, but not sure what the replacement is; correct for LV8.6 - LV14.0
]

FPHP_SectionDef = [
 ["FPHP",	1,0,0,	None], # checked to be the format for LV6.0
 ["FPHb",	7,0,0,	FPHb_Fix], # checked to be the format for LV8.6 - LV14.0
 ["FPHc",	15,0,0,	None], # not sure where the switch happened; LV14.0 supports it, but uses ver b by default
]

BDHP_SectionDef = [
 ["BDHP",	1,0,0,	None], # checked to be the format for LV6.0
 ["BDHb",	7,0,0,	BDHb_Fix], # checked to be the format for LV8.6 - LV14.0
 ["BDHc",	15,0,0,	None], # not sure where the switch happened; LV14.0 supports it, but uses ver b by default
]

LIvi_SectionDef = [
 ["LIvi",	1,0,0,	LIvi_Fix], # not sure where it started; correct for LV8.6 - LV14.0
]

LIfp_SectionDef = [
 ["LIfp",	1,0,0,	LIfp_Fix], # not sure where it started; correct for LV8.6 - LV14.0
]

LIbd_SectionDef = [
 ["LIbd",	1,0,0,	LIbd_Fix], # not sure where it started; correct for LV8.6 - LV14.0
]

DSTM_SectionDef = [
 ["DSTM",	1,0,0,	None], # correct for LV7.1 and below
 ["TM80",	8,0,0,	TM80_Fix], # correct for LV8.0 - LV14.0
]

CONP_SectionDef = [
 ["CONP",	1,0,0,	CONP_Fix], # existed at least from LV6.0
]

CPC2_SectionDef = [
 ["CPC2",	9,0,0,	CPC2_Fix], # does not exist in in LV7.1, found for LV9.0 - LV14.0
]

DTHP_SectionDef = [
 ["DTHP",	1,0,0,	DTHP_Fix], # existed at least from LV6.0
]

DFDS_SectionDef = [
 ["DFDS",	1,0,0,	DFDS_Fix], # existed at least from LV6.0
]

BDPW_SectionDef = [
 ["BDPW",	1,0,0,	BDPW_Fix], # existed at least from LV6.0
]

icl8_SectionDef = [
 ["icl8",	5,0,0,	icl8_Fix], # existed at least from LV6.0
]


def getFirstSection(block_names, RSRC, po):
    # Find all blocks, regardless of version we expect them in
    all_sections = []
    for block_name in block_names:
        all_sections += RSRC.findall("./"+block_name+"/Section")
    if len(all_sections) > 0:
        return all_sections[0]
    return None

def getVersionElement(RSRC, po):
    # Get LV version
    # Find all blocks, regardless of version we expect them in
    all_sections = []
    for sec_name in ("LVSR", "vers", "LVIN",):
        all_sections += RSRC.findall("./"+sec_name+"/Section/Version")
    ver_elem = None
    if len(all_sections) > 0:
        #TODO get mostly used version instead of first one
        ver_elem = all_sections[0]
    if ver_elem is None:
        ver_elem = ET.Element("Version")
        # TODO figure out by existing tags, hard-coding only as last resort
        ver_elem.set("Major", "14")
        ver_elem.set("Minor", "0")
        ver_elem.set("Bugfix", "0")
        ver_elem.set("Stage", "release")
        ver_elem.set("Build", "36")
        ver_elem.set("Flags", "0x0")
    return ver_elem

def versionGreaterOrEq(ver, major,minor,bugfix):
    ver_major = int(ver.get("Major"), 0)
    if ver_major < major: return False
    ver_minor = int(ver.get("Minor"), 0)
    if ver_minor < minor: return False
    ver_bugfix = int(ver.get("Bugfix"), 0)
    if ver_bugfix < bugfix: return False
    return True

def getOrMakeSection(section_def, RSRC, ver, po, allowCreate=True):
    # Find all blocks, regardless of version we expect them in
    all_sections = []
    for sec_d in section_def:
        all_sections += RSRC.findall("./"+sec_d[0]+"/Section")
    if len(all_sections) > 1:
        if (po.verbose > 0):
            eprint("{:s}: Warning: Multiple sections for block <{}> were found"\
              .format(po.xml,section_def[0][0]))
    if len(all_sections) > 0:
        #TODO what if the section doesn't match the version?
        return all_sections[0]
    for sec_d in reversed(section_def):
        if versionGreaterOrEq(ver, sec_d[1],sec_d[2],sec_d[3]):
            break
    if (not allowCreate) and (sec_d[0] not in po.force_recover_section):
        if (po.verbose > 0):
            print("{:s}: No sections found for block <{}>, not creating"\
              .format(po.xml,sec_d[0]))
        return None
    if (po.verbose > 0):
        print("{:s}: No sections found for block <{}>, making new one"\
          .format(po.xml,sec_d[0]))
    block_elem = ET.SubElement(RSRC,sec_d[0])
    section_elem = ET.SubElement(block_elem,"Section")
    section_elem.set("Index","0")
    section_elem.set("Format","inline")
    return section_elem

def getOrMakeSectionVersion(section_def, RSRC, ver, po):
    # Find all blocks, regardless of version we expect them in
    all_sections = []
    for sec_d in section_def:
        all_sections += RSRC.findall("./"+sec_d[0]+"/Section")
    # 'vers' can have multiple sections - no warning if it does
    if len(all_sections) > 0:
        #TODO select best instead of first
        return all_sections[0]
    for sec_d in reversed(section_def):
        if versionGreaterOrEq(ver, sec_d[1],sec_d[2],sec_d[3]):
            break
    if (po.verbose > 0):
        print("{:s}: No sections found for block <{}>, making new one"\
          .format(po.xml,sec_d[0]))
    block_elem = ET.SubElement(RSRC,sec_d[0])
    section_elem = ET.SubElement(block_elem,"Section")
    section_elem.set("Index","0")
    section_elem.set("Format","inline")
    return section_elem

def fixSection(section_def, RSRC, section_elem, ver, po):
    fo = 1 * [None]
    fo[FUNC_OPTS.changed] = False
    for sec_d in reversed(section_def):
        if versionGreaterOrEq(ver, sec_d[1],sec_d[2],sec_d[3]):
            break
    fixFunc = sec_d[4]
    if fixFunc is None:
        if (po.verbose > 0):
            print("{:s}: Block <{}> section has no fixer"\
              .format(po.xml,sec_d[0]))
        return False
    changed = fixFunc(RSRC, section_elem, ver, fo, po)
    if changed:
        if (po.verbose > 0):
            print("{:s}: Block <{}> section updated"\
              .format(po.xml,sec_d[0]))
    else:
        if (po.verbose > 0):
            print("{:s}: Block <{}> section already valid"\
              .format(po.xml,sec_d[0]))
    return fo[FUNC_OPTS.changed]

def makeUidsUnique(FPHP, BDHP, ver, fo, po):
    """ Makes 'uid' values unique in FP and BD

    Removes references to invalid 'uid's from the tree.
    """
    # Prepare list of all elements with 'uid's
    elems = []
    for root in (FPHP, BDHP,):
        elems.extend(root.findall(".//*[@uid]"))
    # List elements in which 'uid's are not unique
    not_unique_elems = []
    for xpath in ("./SL__rootObject/root/ddoList/SL__arrayElement", \
          ".//SL__arrayElement/ddo/ddoList/SL__arrayElement", \
          "./SL__rootObject/root/conPane/cons/SL__arrayElement/ConnectionDCO",):
        not_unique_elems.extend(FPHP.findall(xpath))
    for xpath in ("./SL__rootObject/root/zPlaneList/SL__arrayElement", \
          "./SL__rootObject/root/nodeList/SL__arrayElement/termList/SL__arrayElement/dco",):
        not_unique_elems.extend(BDHP.findall(xpath))
    all_used_uids = set()
    for elem in elems:
        uidStr = elem.get("uid")
        if representsInt(uidStr):
            uid = int(uidStr,0)
            all_used_uids.add(uid)
    used_uids = set()
    used_uids.add(0)
    for elem in elems:
        # Skip elems which we do not expect to be unique
        if elem in not_unique_elems:
            continue
        uidStr = elem.get("uid")
        if representsInt(uidStr):
            uid = int(uidStr,0)
            isCorrect = (uid not in used_uids)
        else:
            uid = max(used_uids)
            isCorrect = False
        if not isCorrect:
            while uid in all_used_uids:
                uid += 1
            elem.set("uid", str(uid))
            fo[FUNC_OPTS.changed] = True
        used_uids.add(uid)
        all_used_uids.add(uid)
    # Now make sure that non-unique elems are not unique
    # First, create a map to help in getting parents of elements
    parent_map = {}
    parent_map.update({c:p for p in FPHP.iter( ) for c in p})
    parent_map.update({c:p for p in BDHP.iter( ) for c in p})
    for elem in not_unique_elems:
        uidStr = elem.get("uid")
        if representsInt(uidStr):
            uid = int(uidStr,0)
            isCorrect = (uid in used_uids)
        else:
            uid = max(used_uids)
            isCorrect = False
        if not isCorrect:
            if (po.verbose > 1):
                print("{:s}: Found reference to non-existing uid={}, removing"\
                  .format(po.xml,uid))
            # remove the reference from tree, moving up to first array; it so happens that all
            # sub-trees which we may want to remove like that are elements of arrays
            child_elem = elem
            parent_elem = parent_map[child_elem]
            while child_elem.tag != "SL__arrayElement":
                child_elem = parent_elem
                parent_elem = parent_map[child_elem]
            parent_elem.remove(child_elem)
            fo[FUNC_OPTS.changed] = True
    # Now re-create required entries in branches which content we have in not_unique_elems
    # Refilling of ddoList - it should have entries for all DDOs
    # There is one root ddoList, and controls which are containers for other controls also have their nested lists
    allDDOsWithLists = []
    allDDOsWithLists.append( FPHP.find("./SL__rootObject/root/ddoList/..") )
    allDDOsWithLists.extend( FPHP.findall(".//SL__arrayElement/ddo/ddoList/..") )
    for ddo in allDDOsWithLists:
        zPlaneList_elems = ddo.findall("./paneHierarchy/zPlaneList/SL__arrayElement[@class][@uid]")
        ddoList = ddo.find("./ddoList")
        for dco_elem in reversed(zPlaneList_elems):
            uidStr = dco_elem.get("uid")
            if representsInt(uidStr):
                uid = int(uidStr,0)
            ddoref = ddoList.find("./SL__arrayElement[@uid='{}']".format(uid))
            if ddoref is None:
                ddoref = ET.SubElement(ddoList, "SL__arrayElement")
                ddoref.set("uid",str(uid))
    # Refilling of conPane - its content should correspond to connectors in VCTP pointed to by CONP, but this data
    # is also a subset of what we have stored in 'root/paneHierarchy/zPlaneList' elements
    zPlaneList_elems = FPHP.findall("./SL__rootObject/root/paneHierarchy/zPlaneList/SL__arrayElement[@class='fPDCO'][@uid]")
    conPane_cons = FPHP.find("./SL__rootObject/root/conPane/cons")
    # Sort the zPlaneList elements on conNum
    zPlaneList_conNums = {}
    for elem in zPlaneList_elems:
        conNum = elem.find("./conNum")
        if conNum is not None:
            conNum = conNum.text
        if conNum is None:
            conNum = 0
        else:
            conNum = int(conNum, 0)
        zPlaneList_conNums[conNum] = elem
    # Check the content to our sorted list
    entryId = 0
    prevConNum = -1
    for conNum in sorted(zPlaneList_conNums.keys()):
        zPlaneElem = zPlaneList_conNums[conNum]
        if conNum < 0: continue

        conUid = zPlaneElem.get("uid")
        if conUid is not None:
            conUid = int(conUid, 0)
        if conUid is None:
            conUid = 0

        arrayElement = conPane_cons.find("./SL__arrayElement["+str(int(entryId+1))+"]")
        if arrayElement is None:
            arrayElement = ET.SubElement(conPane_cons, "SL__arrayElement")
            fo[FUNC_OPTS.changed] = True
        attribGetOrSetDefault(arrayElement, "class", "ConpaneConnection", fo, po)
        if conNum != prevConNum+1:
            attribGetOrSetDefault(arrayElement, "index", conNum, fo, po)

        connectionDCO = elemFindOrCreateWithAttribsAndTags(arrayElement, "ConnectionDCO", \
          ( ("uid", conUid,), ), [], fo, po)

        prevConNum = conNum
        entryId += 1


    return fo[FUNC_OPTS.changed]

def checkBlocksAvailable(root, po):
    """ Check which blocks we have, print proper messages
    """
    RSRC = root
    # Get LV version
    ver = getVersionElement(RSRC, po)
    # Update version section, if required
    vers = getOrMakeSectionVersion(vers_SectionDef, RSRC, ver, po)
    fixSection(vers_SectionDef, RSRC, vers, ver, po)

    LVSR = getOrMakeSection(LVSR_SectionDef, RSRC, ver, po)
    fixSection(LVSR_SectionDef, RSRC, LVSR, ver, po)

    VCTP = getOrMakeSection(VCTP_SectionDef, RSRC, ver, po)
    fixSection(VCTP_SectionDef, RSRC, VCTP, ver, po)

    CPC2 = getOrMakeSection(CPC2_SectionDef, RSRC, ver, po)
    fixSection(CPC2_SectionDef, RSRC, CPC2, ver, po)

    DTHP = getOrMakeSection(DTHP_SectionDef, RSRC, ver, po)
    fixSection(DTHP_SectionDef, RSRC, DTHP, ver, po)

    FPHP = getOrMakeSection(FPHP_SectionDef, RSRC, ver, po)
    fixSection(FPHP_SectionDef, RSRC, FPHP, ver, po)

    BDHP = getOrMakeSection(BDHP_SectionDef, RSRC, ver, po, allowCreate=False)
    if BDHP is not None:
        fixSection(BDHP_SectionDef, RSRC, BDHP, ver, po)

    LIvi = getOrMakeSection(LIvi_SectionDef, RSRC, ver, po)
    fixSection(LIvi_SectionDef, RSRC, LIvi, ver, po)

    LIfp = getOrMakeSection(LIfp_SectionDef, RSRC, ver, po)
    fixSection(LIfp_SectionDef, RSRC, LIfp, ver, po)

    LIbd = getOrMakeSection(LIbd_SectionDef, RSRC, ver, po, allowCreate=False)
    if LIbd is not None:
        fixSection(LIbd_SectionDef, RSRC, LIbd, ver, po)

    DSTM = getOrMakeSection(DSTM_SectionDef, RSRC, ver, po)
    fixSection(DSTM_SectionDef, RSRC, DSTM, ver, po)

    DFDS = getOrMakeSection(DFDS_SectionDef, RSRC, ver, po)
    fixSection(DFDS_SectionDef, RSRC, DFDS, ver, po)

    BDPW = getOrMakeSection(BDPW_SectionDef, RSRC, ver, po)
    fixSection(BDPW_SectionDef, RSRC, BDPW, ver, po)

    icl8 = getOrMakeSection(icl8_SectionDef, RSRC, ver, po)
    fixSection(icl8_SectionDef, RSRC, icl8, ver, po)

    # No BD recovery here - make dummy, disconnected section
    BDHP = ET.Element("Section")

    fo = 1 * [None]
    fo[FUNC_OPTS.changed] = False
    makeUidsUnique(FPHP, BDHP, ver, fo, po)
    recountHeapElements(RSRC, FPHP, ver, fo, po)

    pass

def parseSubXMLs(root, po):
    """ Find blocks which refer to external XMLs, and merges all into one tree.
    """
    for i, block_elem in enumerate(root):
        for k, section_elem in enumerate(block_elem):
            fmt = section_elem.get("Format")
            if fmt == "xml": # Format="xml" - the content is stored in a separate XML file
                if (po.verbose > 1):
                    print("{:s}: For Block {} section {}, reading separate XML file '{}'"\
                      .format(po.xml,block_elem.tag,section_elem.get("Index"),section_elem.get("File")))
                xml_path = os.path.dirname(po.xml)
                if len(xml_path) > 0:
                    xml_fname = xml_path + '/' + section_elem.get("File")
                else:
                    xml_fname = section_elem.get("File")
                section_tree = ET.parse(xml_fname, parser=ET.XMLParser(target=ET.CommentedTreeBuilder()))
                subroot = section_tree.getroot()
                section_elem.append(subroot)
    pass

def resaveSubXMLs(root, po):
    """ Find blocks which refer to external XMLs, and merges all into one tree.
    """
    for i, block_elem in enumerate(root):
        for k, section_elem in enumerate(block_elem):
            fmt = section_elem.get("Format")
            if fmt == "xml": # Format="xml" - the content is stored in a separate XML file
                if (po.verbose > 1):
                    print("{:s}: For Block {} section {}, storing separate XML file '{}'"\
                      .format(po.xml,block_elem.tag,section_elem.get("Index"),section_elem.get("File")))
                xml_path = os.path.dirname(po.xml)
                if len(xml_path) > 0:
                    xml_fname = xml_path + '/' + section_elem.get("File")
                else:
                    xml_fname = section_elem.get("File")
                for subroot in section_elem:
                    ET.pretty_element_tree_heap(subroot)
                    section_tree = ET.ElementTree(subroot)
                    with open(xml_fname, "wb") as xml_fh:
                        section_tree.write(xml_fh, encoding='utf-8', xml_declaration=True)
    pass

def detachSubXMLs(root, po):
    """ Find blocks which refer to external XMLs, detach the merged sub-trees.
    """
    for i, block_elem in enumerate(root):
        for k, section_elem in enumerate(block_elem):
            fmt = section_elem.get("Format")
            if fmt == "xml": # Format="xml" - the content is stored in a separate XML file
                for subroot in section_elem:
                    section_elem.remove(subroot)
    pass

def main():
    """ Main executable function.

    Its task is to parse command line options and call a function which performs requested command.
    """
    # Parse command line options

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('-m', '--xml', default="", type=str,
            help="name of the main XML file of extracted VI dataset")

    parser.add_argument('-v', '--verbose', action='count', default=0,
            help="increases verbosity level; max level is set by -vvv")

    parser.add_argument('--drop-section', action='append', type=str,
            help="name a section to drop just after XML loading")

    parser.add_argument('--force-recover-section', action='append', type=str,
            help="name a section to force re-create even if this may produce damaged file")

    subparser = parser.add_mutually_exclusive_group(required=True)

    subparser.add_argument('-f', '--fix', action='store_true',
            help="fix the file")

    subparser.add_argument('--version', action='version', version="%(prog)s {version} by {author}"
              .format(version=__version__,author=__author__),
            help="display version information and exit")

    po = parser.parse_args()

    # Store base name - without path and extension
    if len(po.xml) > 0:
        po.filebase = os.path.splitext(os.path.basename(po.xml))[0]
    else:
        raise FileNotFoundError("Input XML file was not provided.")

    if po.force_recover_section is None:
        po.force_recover_section = []

    if po.drop_section is None:
        po.drop_section = []

    if po.fix:

        if (po.verbose > 0):
            print("{}: Starting XML file parse for RSRC fix".format(po.xml))
        tree = ET.parse(po.xml, parser=ET.XMLParser(target=ET.CommentedTreeBuilder()))
        root = tree.getroot()
        for blkIdent in po.drop_section:
            sub_elem = root.find("./"+blkIdent)
            if sub_elem is not None:
                root.remove(sub_elem)
        parseSubXMLs(root, po)

        checkBlocksAvailable(root, po)

        resaveSubXMLs(root, po)
        detachSubXMLs(root, po)
        ET.pretty_element_tree_heap(root)
        with open(po.xml, "wb") as xml_fh:
            tree.write(xml_fh, encoding='utf-8', xml_declaration=True)

    else:

        raise NotImplementedError("Unsupported command.")

if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        eprint("Error: "+str(ex))
        raise
        sys.exit(10)
