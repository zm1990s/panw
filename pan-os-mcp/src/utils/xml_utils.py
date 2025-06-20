"""
XML utilities for PAN-OS MCP Server.
Provides helper functions for XML processing.
"""

import logging
import xml.dom.minidom
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("pan-os-mcp.utils")


def prettify_xml(xml_string: str) -> str:
    """
    Prettify an XML string.
    
    Args:
        xml_string: The XML string to prettify
    
    Returns:
        The prettified XML string
    """
    try:
        dom = xml.dom.minidom.parseString(xml_string)
        pretty_xml = dom.toprettyxml(indent="  ")
        return pretty_xml
    except Exception as e:
        logger.warning(f"Failed to prettify XML: {str(e)}")
        return xml_string


def dict_to_xml(data: Dict[str, Any], root_name: str = "root") -> str:
    """
    Convert a dictionary to an XML string.
    
    Args:
        data: The dictionary to convert
        root_name: The name of the root element
    
    Returns:
        The XML string
    """
    root = ET.Element(root_name)
    _build_xml_element(root, data)
    
    # Convert to string
    xml_string = ET.tostring(root, encoding="unicode")
    return xml_string


def _build_xml_element(parent: ET.Element, data: Any) -> None:
    """
    Recursively build XML elements from a dictionary.
    
    Args:
        parent: The parent element
        data: The data to convert
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key.startswith("@"):
                # Handle attributes
                parent.set(key[1:], str(value))
            elif key == "#text":
                # Handle text content
                parent.text = str(value)
            else:
                # Handle nested elements
                child = ET.SubElement(parent, key)
                _build_xml_element(child, value)
    
    elif isinstance(data, list):
        # Handle lists by creating multiple elements with the same tag
        for item in data:
            # Use the parent's tag for list items
            child = ET.SubElement(parent, parent.tag)
            _build_xml_element(child, item)
    
    else:
        # Handle simple values
        parent.text = str(data)


def xml_to_dict(xml_string: str) -> Dict[str, Any]:
    """
    Convert an XML string to a dictionary.
    
    Args:
        xml_string: The XML string to convert
    
    Returns:
        The dictionary representation of the XML
    """
    try:
        root = ET.fromstring(xml_string)
        return _element_to_dict(root)
    except Exception as e:
        logger.error(f"Failed to parse XML: {str(e)}")
        raise ValueError(f"Failed to parse XML: {str(e)}")


def _element_to_dict(element: ET.Element) -> Dict[str, Any]:
    """
    Convert an XML element to a dictionary.
    
    Args:
        element: The XML element to convert
    
    Returns:
        The dictionary representation of the element
    """
    result = {}
    
    # Process attributes
    for key, value in element.attrib.items():
        result[f"@{key}"] = value
    
    # Process children
    for child in element:
        child_dict = _element_to_dict(child)
        
        if child.tag in result:
            # If the tag already exists, convert to a list if not already
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_dict)
        else:
            result[child.tag] = child_dict
    
    # Process text content
    if element.text and element.text.strip():
        if result:  # If we have attributes or children
            result["#text"] = element.text.strip()
        else:  # Just text content
            return element.text.strip()
    
    return result


def validate_xml(xml_string: str) -> bool:
    """
    Validate an XML string.
    
    Args:
        xml_string: The XML string to validate
    
    Returns:
        True if the XML is valid, False otherwise
    """
    try:
        ET.fromstring(xml_string)
        return True
    except Exception as e:
        logger.warning(f"XML validation failed: {str(e)}")
        return False
