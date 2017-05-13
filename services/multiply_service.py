#!/usr/bin/python
import urlparse

import constants
import util
from service_base import ServiceBase


class MultiplyService(ServiceBase):
    @staticmethod
    def name():
        return "/mul"

    def __init__(
        self,
    ):
        super(MultiplyService, self).__init__()

    def before_response_headers(
        self,
        request_context,
    ):
        try:
            qs = urlparse.parse_qs(request_context["parsed"].query)
            result = int(qs['a'][0]) * int(qs['b'][0])
            message = util.text_to_html(
                "The result is %s, my boy." % (result)
            )

        except Exception as e:
            request_context["code"] = 500
            request_context["status"] = constants.INTERNAL_ERROR
            message = util.text_to_html(
                str(e)
            )

        request_context["response"] = message
        request_context["headers"][constants.CONTENT_LENGTH] = len(message)
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"
