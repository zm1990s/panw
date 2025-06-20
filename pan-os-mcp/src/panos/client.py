"""
PAN-OS client implementation.
Handles communication with PAN-OS devices using the XML API.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from requests.exceptions import RequestException

logger = logging.getLogger("pan-os-mcp.panos")


class PANOSClient:
    """
    Client for interacting with PAN-OS devices using the XML API.
    """

    def __init__(
        self,
        hostname: str,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verify_ssl: bool = True,
        timeout: int = 30,
    ):
        """
        Initialize the PAN-OS client.
        
        Args:
            hostname: IP address or hostname of the PAN-OS device
            api_key: API key for authentication (preferred)
            username: Username for authentication (if api_key not provided)
            password: Password for authentication (if api_key not provided)
            verify_ssl: Whether to verify SSL certificates
            timeout: Request timeout in seconds
        """
        self.hostname = hostname
        self.api_key = api_key
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.base_url = f"https://{hostname}/api/"
        
        if not api_key and not (username and password):
            raise ValueError("Either api_key or username/password must be provided")
        
        logger.info(f"Initialized PAN-OS client for {hostname}")

    def _generate_api_key(self) -> str:
        """
        Generate an API key using username and password.
        
        Returns:
            The generated API key
        
        Raises:
            ValueError: If authentication fails
        """
        if not self.username or not self.password:
            raise ValueError("Username and password are required to generate API key")
        
        params = {
            "type": "keygen",
            "user": self.username,
            "password": self.password
        }
        
        try:
            response = requests.get(
                self.base_url,
                params=params,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Parse the XML response
            root = ET.fromstring(response.text)
            status = root.find(".//status")
            if status is not None and status.text == "success":
                key_element = root.find(".//key")
                if key_element is not None and key_element.text:
                    self.api_key = key_element.text
                    logger.info("Successfully generated API key")
                    return self.api_key
            
            error_msg = root.find(".//msg")
            if error_msg is not None and error_msg.text:
                raise ValueError(f"Failed to generate API key: {error_msg.text}")
            else:
                raise ValueError("Failed to generate API key: Unknown error")
        
        except RequestException as e:
            logger.error(f"Request error while generating API key: {str(e)}")
            raise ValueError(f"Failed to connect to PAN-OS device: {str(e)}")
        
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {str(e)}")
            raise ValueError(f"Failed to parse response from PAN-OS device: {str(e)}")

    def _make_request(
        self,
        request_type: str,
        action: Optional[str] = None,
        xpath: Optional[str] = None,
        element: Optional[str] = None,
        cmd: Optional[str] = None,
        extra_params: Optional[Dict[str, str]] = None
    ) -> ET.Element:
        """
        Make a request to the PAN-OS XML API.
        
        Args:
            request_type: The type of request (e.g., 'config', 'op', 'commit')
            action: The action to perform (e.g., 'get', 'set', 'delete')
            xpath: The XPath for the configuration
            element: The XML element to set or edit
            cmd: The operational command to execute
            extra_params: Additional parameters to include in the request
        
        Returns:
            The XML response as an ElementTree Element
        
        Raises:
            ValueError: If the request fails
        """
        # Ensure we have an API key
        if not self.api_key and self.username and self.password:
            self._generate_api_key()
        
        if not self.api_key:
            raise ValueError("API key is required for making requests")
        
        # Build request parameters
        params = {
            "key": self.api_key,
            "type": request_type
        }
        
        if action:
            params["action"] = action
        
        if xpath:
            params["xpath"] = xpath
        
        if element:
            params["element"] = element
        
        if cmd:
            params["cmd"] = cmd
        
        if extra_params:
            params.update(extra_params)
        
        try:
            logger.debug(f"Making request: type={request_type}, action={action}")
            response = requests.get(
                self.base_url,
                params=params,
                verify=self.verify_ssl,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Parse the XML response
            root = ET.fromstring(response.text)
            
            # Check for errors
            status = root.find(".//status")
            if status is not None and status.text != "success":
                error_msg = root.find(".//msg")
                if error_msg is not None and error_msg.text:
                    raise ValueError(f"PAN-OS API error: {error_msg.text}")
                else:
                    raise ValueError("PAN-OS API error: Unknown error")
            
            return root
        
        except RequestException as e:
            logger.error(f"Request error: {str(e)}")
            raise ValueError(f"Failed to connect to PAN-OS device: {str(e)}")
        
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {str(e)}")
            raise ValueError(f"Failed to parse response from PAN-OS device: {str(e)}")

    def get_system_info(self) -> Dict[str, Any]:
        """
        Get system information from the PAN-OS device.
        
        Returns:
            Dictionary containing system information
        """
        cmd = "<show><system><info></info></system></show>"
        root = self._make_request("op", cmd=cmd)
        
        # Extract system info
        system_info = {}
        info_element = root.find(".//system")
        
        if info_element is not None:
            for child in info_element:
                if child.tag and child.text:
                    system_info[child.tag] = child.text
        
        return system_info

    def execute_op_command(self, cmd: str) -> Dict[str, Any]:
        """
        Execute an operational command.
        
        Args:
            cmd: The XML command to execute
        
        Returns:
            Dictionary containing the command result
        """
        root = self._make_request("op", cmd=cmd)
        
        # Convert the XML response to a dictionary
        result = self._xml_to_dict(root)
        return result

    def get_configuration(self, xpath: str) -> Dict[str, Any]:
        """
        Get configuration from the specified XPath.
        
        Args:
            xpath: The XPath to the configuration
        
        Returns:
            Dictionary containing the configuration
        """
        root = self._make_request("config", action="get", xpath=xpath)
        
        # Convert the XML response to a dictionary
        result = self._xml_to_dict(root)
        return result

    def set_configuration(self, xpath: str, element: str) -> Dict[str, Any]:
        """
        Set configuration at the specified XPath.
        
        Args:
            xpath: The XPath where to set the configuration
            element: The XML element to set
        
        Returns:
            Dictionary containing the result
        """
        root = self._make_request("config", action="set", xpath=xpath, element=element)
        
        # Convert the XML response to a dictionary
        result = self._xml_to_dict(root)
        return result

    def edit_configuration(self, xpath: str, element: str) -> Dict[str, Any]:
        """
        Edit configuration at the specified XPath.
        
        Args:
            xpath: The XPath to the configuration to edit
            element: The XML element with the new configuration
        
        Returns:
            Dictionary containing the result
        """
        root = self._make_request("config", action="edit", xpath=xpath, element=element)
        
        # Convert the XML response to a dictionary
        result = self._xml_to_dict(root)
        return result

    def delete_configuration(self, xpath: str) -> Dict[str, Any]:
        """
        Delete configuration at the specified XPath.
        
        Args:
            xpath: The XPath to the configuration to delete
        
        Returns:
            Dictionary containing the result
        """
        root = self._make_request("config", action="delete", xpath=xpath)
        
        # Convert the XML response to a dictionary
        result = self._xml_to_dict(root)
        return result

    def commit(self, force: bool = False, partial: Optional[str] = None) -> Dict[str, Any]:
        """
        Commit the candidate configuration.
        
        Args:
            force: Whether to force the commit
            partial: XML for partial commit
        
        Returns:
            Dictionary containing the commit result
        """
        extra_params = {}
        
        if force:
            extra_params["cmd"] = "<commit><force></force></commit>"
        elif partial:
            extra_params["cmd"] = f"<commit>{partial}</commit>"
        else:
            extra_params["cmd"] = "<commit></commit>"
        
        root = self._make_request("commit", **extra_params)
        
        # Convert the XML response to a dictionary
        result = self._xml_to_dict(root)
        
        # Check if this is an async job
        job_id = root.find(".//job")
        if job_id is not None and job_id.text:
            result["job_id"] = job_id.text
        
        return result

    def check_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Check the status of an asynchronous job.
        
        Args:
            job_id: The ID of the job to check
        
        Returns:
            Dictionary containing the job status
        """
        cmd = f"<show><jobs><id>{job_id}</id></jobs></show>"
        root = self._make_request("op", cmd=cmd)
        
        # Convert the XML response to a dictionary
        result = self._xml_to_dict(root)
        return result

    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """
        Convert an XML element to a dictionary.
        
        Args:
            element: The XML element to convert
        
        Returns:
            Dictionary representation of the XML
        """
        result = {}
        
        # Process attributes
        for key, value in element.attrib.items():
            result[f"@{key}"] = value
        
        # Process children
        for child in element:
            child_dict = self._xml_to_dict(child)
            
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
