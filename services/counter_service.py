#!/usr/bin/python
import Cookie

import constants
import util
from service_base import ServiceBase

class CounterService(ServiceBase):
    @staticmethod
    def name():
        return "/counter"

    def __init__(
        self,
    ):
        super(CounterService, self).__init__()

    def before_request_content(
        self,
        request_context,
    ):
        c = Cookie.SimpleCookie()
        try:
            c.load(str(request_context["req_headers"].get(constants.Cookie)))
            if "counter" in c.keys():
                counter = c["counter"].value
            else:
                counter = 0
            c["counter"] = str(int(counter)+1)
            splitted = str(c["counter"]).split(":")
            request_context["counter"] = counter
            request_context["headers"][splitted[0]] = splitted[1]

        except Exception as e:
            request_context["code"] = 500
            request_context["status"] = constants.INTERNAL_ERROR
            request_context["counter"] = str(e)

    def before_response_headers(
        self,
        request_context,
    ):
        request_context["response"] = util.text_to_html(
            request_context["counter"]
        )
        request_context["headers"][constants.CONTENT_LENGTH] = len(request_context["response"])
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"

    def get_header_dict(
        self,
    ):
        return {
            "Cookie":None
        }
