# -*- coding: utf-8 -*-

""" LabView RSRC file xml support.

XML input/output support. Wrapped Python libraries, with any neccessary changes.
"""

# Copyright (C) 2019 Mefistotelis <mefistotelis@gmail.com>
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

import xml.etree.ElementTree as ET
from xml.etree.ElementTree import ElementTree,Element,Comment,SubElement,XMLParser

class BinCompatTreeBuilder:
    """Generic element structure builder.

    This builder converts a sequence of start, data, and end method
    calls to a well-formed element structure.

    You can use this class to build an element structure using a custom XML
    parser, or a parser for some other XML-like format.

    *element_factory* is an optional element factory which is called
    to create new Element instances, as necessary.

    *comment_factory* is a factory to create comments to be used instead of
    the standard factory.  If *insert_comments* is false (the default),
    comments will not be inserted into the tree.

    *pi_factory* is a factory to create processing instructions to be used
    instead of the standard factory.  If *insert_pis* is false (the default),
    processing instructions will not be inserted into the tree.
    """
    def __init__(self, element_factory=None, *,
                 comment_factory=None, pi_factory=None,
                 insert_comments=False, insert_pis=False):
        self._data = [] # data collector
        self._elem = [] # element stack
        self._last = None # last element
        self._root = None # root element
        self._tail = None # true if we're after an end tag
        if comment_factory is None:
            comment_factory = Comment
        self._comment_factory = comment_factory
        self.insert_comments = insert_comments
        if pi_factory is None:
            pi_factory = ET.ProcessingInstruction
        self._pi_factory = pi_factory
        self.insert_pis = insert_pis
        if element_factory is None:
            element_factory = Element
        self._factory = element_factory

    def close(self):
        """Flush builder buffers and return toplevel document Element."""
        assert len(self._elem) == 0, "missing end tags"
        assert self._root is not None, "missing toplevel element"
        return self._root

    def _flush(self):
        if self._data:
            if self._last is not None:
                text = "".join(self._data)
                if self._tail:
                    assert self._last.tail is None, "internal error (tail)"
                    self._last.tail = text
                else:
                    assert self._last.text is None, "internal error (text)"
                    self._last.text = text
            self._data = []

    def data(self, data):
        """Add text to current element.

        NOTE: The change is here! This is the only method modified from original
        implementation taken from Python 3.8. The change is to un-escape binary
        characters; but also, since these data is parsed by chunks, data from
        previous chunk may be required to un-escape next one. And this is why
        we need custom implementation of this class.
        """
        unescaped_data = None
        if len(self._data) > 0:
            last_data = self._data[-1]
            if len(last_data) < 6 and '&' in last_data:
                self._data.pop()
                unescaped_data = unescape_cdata_control_chars(last_data+data)
        if unescaped_data is None:
            unescaped_data = unescape_cdata_control_chars(data)
        # If we have '&' near end, append that part separately - we may want modify it next time
        if '&' in unescaped_data[-5:]:
            self._data.append(unescaped_data[:-5])
            self._data.append(unescaped_data[-5:])
        else:
            self._data.append(unescaped_data)

    def start(self, tag, attrs):
        """Open new element and return it.

        *tag* is the element name, *attrs* is a dict containing element
        attributes.

        """
        self._flush()
        self._last = elem = self._factory(tag, attrs)
        if self._elem:
            self._elem[-1].append(elem)
        elif self._root is None:
            self._root = elem
        self._elem.append(elem)
        self._tail = 0
        return elem

    def end(self, tag):
        """Close and return current Element.

        *tag* is the element name.

        """
        self._flush()
        self._last = self._elem.pop()
        assert self._last.tag == tag,\
               "end tag mismatch (expected %s, got %s)" % (
                   self._last.tag, tag)
        self._tail = 1
        return self._last

    def comment(self, text):
        """Create a comment using the comment_factory.

        *text* is the text of the comment.
        """
        return self._handle_single(
            self._comment_factory, self.insert_comments, text)

    def pi(self, target, text=None):
        """Create a processing instruction using the pi_factory.

        *target* is the target name of the processing instruction.
        *text* is the data of the processing instruction, or ''.
        """
        return self._handle_single(
            self._pi_factory, self.insert_pis, target, text)

    def _handle_single(self, factory, insert, *args):
        elem = factory(*args)
        if insert:
            self._flush()
            self._last = elem
            if self._elem:
                self._elem[-1].append(elem)
            self._tail = 1
        return elem

# Use parse(source, parser=ET.XMLParser(target=ET.CommentedTreeBuilder())) to get the XML with comments retained
class CommentedTreeBuilder(BinCompatTreeBuilder):
    def comment(self, data):
        self.start(Comment, {})
        self.data(data)
        self.end(Comment)

    def data(self, data):
        """Add text to current element."""
        super().data(unescape_cdata_control_chars(data))


def parse(source, parser=None):
    """Parse XML document into element tree.

    *source* is a filename or file object containing XML data,
    *parser* is an optional parser instance defaulting to XMLParser.

    Return an ElementTree instance.

    """
    if parser is None:
        parser = XMLParser(target=BinCompatTreeBuilder())
    return ET.parse(source, parser)

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
            import string
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

def escape_attribute_control_chars(text):
    """ escape control characters

    Within attributes, white spaces are normalized, including tabs.
    We need to escape all of these.
    """
    ccList = ( i for i in range(0,32) )
    return escape_cdata_custom_chars(text, ccList)

def unescape_attribute_control_chars(text):
    """ un-escape control characters
    """
    ccList = ( i for i in range(0,32) )
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

ET._original_escape_cdata = ET._escape_cdata

def _escape_cdata(text):
    # escape character data
    try:
        if any(chr(c) in text for c in [c for c in range(0,32) if c not in (ord("\n"), ord("\t"),)]):
            return "<![CDATA[" + escape_cdata_control_chars(text) + "]]>"
    except (TypeError, AttributeError):
        ET._raise_serialization_error(text)
    return ET._original_escape_cdata(text)
ET._escape_cdata = _escape_cdata

# Escaping attributes really also requires changes in parsing, which aren't really possible
# as ElementTree uses native XML parser library; that library interprets the HTML entity numbers
# and fails the parsing because it receives characters which cannot be stored in XML
# we could workaround it though, by using escaping into something else than HTML entity numbers
ET._original_escape_attrib = ET._escape_attrib

def _escape_attrib(text):
    # escape character data
    try:
        # Copied from _original_escape_attrib
        if "&" in text:
            text = text.replace("&", "&amp;")
        if "<" in text:
            text = text.replace("<", "&lt;")
        if ">" in text:
            text = text.replace(">", "&gt;")
        if "\"" in text:
            text = text.replace("\"", "&quot;")
        # Additionally, change control chars to entity numbers
        if any(chr(c) in text for c in [c for c in range(0,32)]):
            return escape_attribute_control_chars(text)
    except (TypeError, AttributeError):
        ET._raise_serialization_error(text)
    return text #ET._original_escape_attrib(text)
ET._escape_attrib = _escape_attrib

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

def safe_store_element_text(elem, text):
    elem.text = text

def unescape_safe_store_element_text(elem_text):
    return elem_text
