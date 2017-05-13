#!/usr/bin/python
import time

import constants
import util
from service_base import ServiceBase


class ClockService(ServiceBase):
    @staticmethod
    def name():
        return "/clock"

    def __init__(
        self,
    ):
        super(ClockService, self).__init__()

    def before_response_headers(
        self,
        request_context,
    ):
        message = util.text_to_html(
            time.strftime("%H:%M:%S", time.localtime())
        )
        request_context["response"] = message
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        super(ClockService, self).before_response_headers(request_context)
