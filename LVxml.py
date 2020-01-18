# -*- coding: utf-8 -*-

""" LabView RSRC file xml support.

XML input/output support. Wrapped Python libraries, with any neccessary changes.
"""

# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree,Element,Comment,SubElement,parse

def et_escape_cdata_mind_binary(text):
    # escape character data
    try:
        if True:
            if "&" in text:
                text = text.replace("&", "&amp;")
            if "<" in text:
                text = text.replace("<", "&lt;")
            if ">" in text:
                text = text.replace(">", "&gt;")
            #if '"' in text:
            #    text = text.replace('"', "&quot;")
            for i in range(0,32):
                if i in [ord("\n"),ord("\t")]: continue
                text = text.replace(chr(i), "&#x{:02X};".format(i))
        return text
    except (TypeError, AttributeError):
        ET._raise_serialization_error(text)

#ET._escape_cdata = LVmisc.et_escape_cdata_mind_binary

def escape_cdata_custom_chars(text, ccList):
    """ escape character data
    """
    try:
        if True:
            for i in ccList:
                text = text.replace(chr(i), "&#x{:02X};".format(i))
        return text
    except (TypeError, AttributeError):
        #ET._raise_serialization_error(text)
        raise TypeError(
            "cannot escape for serialization %r (type %s)" % (text, type(text).__name__)
            )

def unescape_cdata_custom_chars(text, ccList):
    """ un-escape character data
    """
    try:
        if True:
            for i in ccList:
                text = text.replace("&#x{:02X};".format(i), chr(i))
        return text
    except (TypeError, AttributeError):
        #ET._raise_serialization_error(text)
        raise TypeError(
            "cannot unescape after deserialize %r (type %s)" % (text, type(text).__name__)
            )

def escape_cdata_control_chars(text):
    """ escape control characters
    """
    ccList = ( i for i in range(0,32) if i not in (ord("\n"), ord("\t"),) )
    return escape_cdata_custom_chars(text, ccList)

def unescape_cdata_control_chars(text):
    """ un-escape control characters
    """
    ccList = ( i for i in range(0,32) if i not in (ord("\n"), ord("\t"),) )
    return unescape_cdata_custom_chars(text, ccList)

def CDATA(text=None):
    """
    A CDATA element factory function that uses the function itself as the tag
    (based on the Comment factory function in the ElementTree implementation).
    """
    element = ET.Element('![CDATA[')
    element.text = text
    return element

ET._original_serialize_xml = ET._serialize_xml

def _serialize_xml(write, elem, qnames, namespaces,
                   short_empty_elements, **kwargs):
    if elem.tag == '![CDATA[':
        write("<" + elem.tag)
        if elem.text:
            write(elem.text)
        write("]]>")
        if elem.tail:
            write(elem.tail)
        return
    return ET._original_serialize_xml(
          write, elem, qnames, namespaces,
          short_empty_elements, **kwargs)
ET._serialize_xml = ET._serialize['xml'] = _serialize_xml

def pretty_element_tree_heap(elem, level=0):
    """ Pretty ElementTree for LV Heap XML data.

    Does prettying of questionable quality, but prepared
    in a way which simulates how LabVIEW does that to heap.
    """
    elem.tail = "\n" + "".join([ "  " * level ])
    if len(elem) == 1 and elem[0].tag == '![CDATA[':
        return # Don't put spaces around CDATA, treat is as clear text
    if len(elem) > 0 and elem.text is None:
        elem.text = "\n" + "".join([ "  " * (level+1) ])
    for subelem in elem:
        pretty_element_tree_heap(subelem, level+1)
    pass

