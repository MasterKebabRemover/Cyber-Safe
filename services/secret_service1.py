#!/usr/bin/python
import base64

import constants
import util
from service_base import ServiceBase


class SecretService1(ServiceBase):
    @staticmethod
    def name():
        return "/secret1"

    def __init__(
        self,
    ):
        super(SecretService1, self).__init__()

    def before_response_status(
        self,
        request_context,
    ):
        success = False
        authorization_header = request_context["req_headers"].get(
            constants.AUTHORIZATION)
        if authorization_header and authorization_header.split()[0] == "Basic":
            authorization = authorization_header.split("Basic ")[1]
            user, password = base64.b64decode(authorization).split(":", 1)
            if constants.USERS.get(user) == password:
                success = True
                request_context["user"] = user
        if not success:
            request_context["code"] = 401
            request_context["status"] = "Unathorized"
            request_context["headers"] = {
                "WWW-Authenticate": "Basic",
            }

    def before_response_headers(
        self,
        request_context,
    ):
        if request_context.get("user"):
            request_context["response"] = util.text_to_html(
                "Welcome, %s!" % (request_context.get("user"))
            )
            request_context["headers"][constants.CONTENT_LENGTH] = len(
                request_context["response"])
            request_context["headers"][constants.CONTENT_TYPE] = "text/html"

    def get_header_dict(
        self,
    ):
        return {
            constants.AUTHORIZATION: None,
        }
