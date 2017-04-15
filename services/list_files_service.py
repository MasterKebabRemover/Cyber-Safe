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

FORM_HEAD = "<h1>File List:</h1><form>"
FORM_ENTRY = "<input type=\"radio\" name=\"filename\" value=\"R1\"> R2<br>"
FORM_ENDING = (
    "<br><font size=\"5\">Operations: </font><ul>" + 
    "<li><input type=\"submit\" formaction=\"download\" formmethod=\"get\" value=\"Download\"></li>" +
    "<li><input type=\"submit\" formaction=\"delete\" formmethod=\"get\" value=\"Delete\"></li>" +
    "</ul></form><br>" +
    "<font size=\"5\">File Upload: </font><br><br>" +
    "<form action=\"fileupload\" enctype=\"multipart/form-data\" method=\"post\">" +
    "<input type=\"file\" name=\"fileupload\"><br><br>" + 
    "<input type=\"submit\" value=\"Submit\"></form>"
)

class ListFiles(ServiceBase):
    @staticmethod
    def name():
        return "/list"

    def __init__(
        self,
    ):
        super(ListFiles, self).__init__()

    def before_request_content(
        self,
        request_context,
    ):
        request_context["state"] = constants.SLEEPING
        request_context["wake_up_function"] = self._after_root
        util.init_client(
            request_context=request_context,
            client_action=constants.READ,
            client_block_num=1,
        )

    def _after_root(
        self,
        request_context,
    ):
        self._root = request_context["block"]
        file_list = FORM_HEAD
        index = 0
        while index < len(self._root):
            current_name = bytearray(self._root[index:index + constants.FILENAME_LENGTH])
            current_name = current_name.rstrip('\x00')
            if current_name != "":
                file_list += FORM_ENTRY.replace("R1", current_name).replace("R2", current_name)
            index += constants.ROOT_ENTRY_SIZE
        file_list += FORM_ENDING
        request_context["response"] = util.text_to_html(file_list)

    def before_response_headers(
        self,
        request_context,
    ):
        request_context["headers"][constants.CONTENT_LENGTH] = len(request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
