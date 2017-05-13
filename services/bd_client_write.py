#!/usr/bin/python
import logging

import constants
from service_base import ServiceBase


class BDClientWrite(ServiceBase):
    @staticmethod
    def name():
        return constants.WRITE

    def __init__(
        self,
        request_context,
    ):
        cmd = "GET /%s?block=%d %s\r\n" % (
            "write",
            request_context["block_num"],
            constants.HTTP_SIGNATURE
        )
        request_context["send_buffer"] += cmd

    def before_response_headers(
        self,
        request_context,
    ):
        request_context["headers"][constants.CONTENT_LENGTH] = constants.BLOCK_SIZE

    def response(
        self,
        request_context,
    ):
        if request_context["block"]:
            data = request_context["block"]
            request_context["block"] = ""
            return data
        else:
            return None

    def before_terminate(
        self,
        request_context,
    ):
        request_context["parent"].on_finish()

    def get_header_dict(
        self,
    ):
        return {
            constants.CONTENT_LENGTH: 0
        }
