#!/usr/bin/python
import errno
import os
import tempfile
import logging
import socket
import struct
import urlparse

import block_util
import constants
import util
from util import HTTPError
import integration_util
from service_base import ServiceBase
from http_client import HttpClient

class InitService(ServiceBase):
    @staticmethod
    def name():
        return "/init"


    def before_request_content(
        self,
        request_context,
    ):
        authorization = self.get_authorization(request_context)
        if authorization != request_context["app_context"]["admin"]:
            raise util.HTTPError(500, "Internal Error", "Admin password required to init disk")
        else:
            block_util.bd_action(
                request_context=request_context,
                block_num=0,
                action=constants.WRITE,
                block=bytearray(4096),
            )
            block_util.bd_action(
                request_context=request_context,
                block_num=1,
                action=constants.WRITE,
                block=bytearray(4096),
            )

    def before_response_headers(
        self,
        request_context,
    ):

        request_context["response"] = "disk initialized successfuly"
        request_context["response"] += constants.BACK_TO_LIST
        request_context["response"] = util.text_to_html(request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(InitService, self).before_response_headers(request_context)
