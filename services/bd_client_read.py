#!/usr/bin/python
import logging

import constants
from service_base import ServiceBase

class BDClientRead(ServiceBase):
    @staticmethod
    def name():
        return constants.READ

    def __init__(
        self,
        request_context,
    ):
        cmd = "GET /%s?block=%d %s\r\n\r\n" % (
            "read",
            request_context["block_num"],
            constants.HTTP_SIGNATURE
        )
        request_context["send_buffer"] += cmd
        

    def before_request_content(
        self,
        request_context,
    ):
        super(BDClientRead, self).before_request_content(request_context)
        request_context["block"] = ""

    def handle_content(
        self,
        request_context,
    ):
        data = request_context["recv_buffer"][:request_context["content_length"]]
        request_context["recv_buffer"] = request_context["recv_buffer"][len(data):]
        request_context["block"] += data
        request_context["content_length"] -= len(data)
        if len(request_context["block"]) == constants.BLOCK_SIZE:
            return None
        else:
            return bool(request_context["recv_buffer"])

    # def before_response_status(
        # self,
        # request_context,
    # ):
        # cmd = "GET /%s?block=%d %s\r\n\r\n" % (
            # "read",
            # request_context["block_num"],
            # constants.HTTP_SIGNATURE
        # )
        # request_context["send_buffer"] += cmd

    def before_response_headers(
        self,
        request_context,
    ):
        return # must have his to override base

    def before_terminate(
        self,
        request_context,
    ):
        request_context["parent"].on_finish(block=request_context["block"])
    
    def get_header_dict(
        self,
    ):
        return {
            constants.CONTENT_LENGTH:0
        }
