#!/usr/bin/python

import constants
import util
from service_base import ServiceBase

class SecretService2(ServiceBase):
    @staticmethod
    def name():
        return "/secret2"

    def __init__(
        self,
    ):
        super(SecretService2, self).__init__()

    def get_header_dict(
        self,
    ):
        return{
            constants.Cookie: None,
        }

    def before_response_status(
        self,
        request_context,
    ):
        random = util.parse_cookies(request_context["req_headers"].get(constants.Cookie), "random")
        user = request_context["accounts"].get(random)
        if user:
            message = "Welcome, %s!" % (user)
            request_context["response"] = util.text_to_html(
                message,
            )
            request_context["headers"][constants.CONTENT_LENGTH] = len(
                request_context["response"]
            )
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"
        else:
            request_context["code"] = 307
            request_context["status"] = "Temporary Redirect"
            request_context["headers"]["Location"] = "http://localhost:8888/loginform.html"
