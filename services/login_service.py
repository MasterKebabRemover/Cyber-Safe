#!/usr/bin/python
import urlparse

import constants
import util
from service_base import ServiceBase


class LoginService(ServiceBase):
    @staticmethod
    def name():
        return "/login"

    def __init__(
        self,
    ):
        super(LoginService, self).__init__()

    def before_response_headers(
        self,
        request_context,
    ):
        qs = urlparse.parse_qs(
            request_context["parsed"].query
        )
        user, password = qs["user"][0], qs["password"][0]
        cookies_to_set = {}
        code, status = 401, constants.UNATHORIZED
        message = "User and password incorrect"
        if constants.USERS.get(user) == password:
            cookie = util.random_cookie()

            for c, u in request_context["accounts"].copy().iteritems():
                if u == user:
                    del request_context["accounts"][c]

            request_context["accounts"][cookie] = user
            message = "Welcome, %s!" % (user)
            code, status = 200, "OK"
            cookies_to_set = "random=%s" % (cookie)
        request_context["code"] = code
        request_context["status"] = status
        request_context["headers"]["Set-Cookie"] = cookies_to_set
        request_context["response"] = util.text_to_html(message)
        request_context["headers"][constants.CONTENT_LENGTH] = len(
            request_context["response"],
        )
        request_context["headers"][constants.CONTENT_TYPE] = "text/html"

    def get_header_dict(
        self,
    ):
        return{}
