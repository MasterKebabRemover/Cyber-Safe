#!/usr/bin/python
import errno
import os
import socket
import struct
import logging

import constants
import util
from util import HTTPError
from service_base import ServiceBase
from http_client import HttpClient
import block_util

FORM_HEAD = (
    "<h1>File List:</h1><form>" + 
    "<table border=\"1\"><tr>" + 
    "<th>File Name</th><th>File Size (Bytes)</th>" + 
    "</tr>"
)

FORM_ENTRY = (
    "<tr><td><div class=\"radio\">" + 
    "<label><input type=\"radio\" value=\"R1\" name=\"filename\">R1</label></div></td>" + 
    "<td><div class=\"radiotext\">" + 
    "<label for=\"regular\">R2</label></div></td></tr>"
)

FORM_ENDING = (
    "</table>" + 
    "<br><font size=\"5\">Operations: </font><ul>" + 
    "<li><input type=\"submit\" formaction=\"download\" formmethod=\"get\" value=\"Download\"></li>" +
    "<li><input type=\"submit\" formaction=\"delete\" formmethod=\"get\" value=\"Delete\"></li>" +
    "</ul></form><br>" +
    "<font size=\"5\">File Upload: </font><br>" +
    "<form action=\"fileupload\" enctype=\"multipart/form-data\" method=\"post\">" +
    "<input type=\"file\" name=\"fileupload\"><br><br>" + 
    "<input type=\"submit\" value=\"Submit\"></form>"
)

class ListFiles(ServiceBase):
    @staticmethod
    def name():
        return "/list"

    def before_request_content(
        self,
        request_context,
    ):
        block_util.bd_action(
            request_context=request_context,
            block_num=1,
            action=constants.READ,
            service_wake_up=self._after_root,
        )

    def _after_root(
        self,
        request_context,
    ):
        self._root = request_context["block"]
        file_list = FORM_HEAD
        index = 0
        while index < len(self._root):
            entry = util.parse_root_entry(self._root[index: index + constants.ROOT_ENTRY_SIZE])
            if entry["name"] != "":
                file_list += FORM_ENTRY.replace("R1", entry["name"]).replace("R2", str(entry["size"]))
            index += constants.ROOT_ENTRY_SIZE
        file_list += FORM_ENDING
        request_context["response"] = util.text_to_html(file_list)

    def before_response_headers(
        self,
        request_context,
    ):
        request_context["headers"][constants.CONTENT_LENGTH] = len(request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
