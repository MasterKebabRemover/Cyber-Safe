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
from encryption_util import sha
import block_util


class AdminService(ServiceBase):
    @staticmethod
    def name():
        return "/admin"

    def before_request_content(
        self,
        request_context,
    ):
        if self.get_authorization(request_context) != request_context["app_context"]["admin"]:
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
            raise util.HTTPError(500, "Internal Error", util.text_to_css("Admin password required", error=True))
        request_context["code"] = 307
        request_context["status"] = "Temporary Redirect"
        request_context["headers"]["Location"] = "admin.html"
