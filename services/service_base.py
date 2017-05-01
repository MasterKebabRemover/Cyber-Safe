#!/usr/bin/python
import logging
import urlparse

import constants
import util

class ServiceBase(object):
    @staticmethod
    def name():
        return None

    def __init__(
        self,
        request_context=None,
    ):
        pass

    def before_request_headers(
        self,
        request_context,
    ):
        pass

    def before_request_content(
        self,
        request_context,
    ):
        pass

    def handle_content(
        self,
        request_context,
    ):
        pass

    def before_response_status(
        self,
        request_context,
    ):
        pass

    def before_response_headers(
        self,
        request_context,
    ):
        if constants.CONTENT_LENGTH not in request_context["headers"]:
            request_context["headers"][constants.CONTENT_LENGTH] = len(
                    request_context["response"]
                )

    def before_response_content(
        self,
        request_context,
    ):
        pass

    def response(
        self,
        request_context,
    ):
        pass

    def before_terminate(
        self,
        request_context,
    ):
        pass
    
    def get_header_dict(
        self,
    ):
        return {
            constants.CONTENT_LENGTH:0,
            constants.Cookie: None,
        }

    def get_authorization(
        self,
        request_context,
    ):
        # check query and cookie headers. if neither exist, raise error. if any exists, put it in request_context and return it.
        authorization = None
        qs = urlparse.parse_qs(request_context["parsed"].query)
        authorization = qs.get('password', [None, None])[0]

        got_from_cookie = False
        if authorization is None:
            authorization = util.parse_cookies(request_context["req_headers"].get(constants.Cookie), "password")
            got_from_cookie = True

        if authorization:
            request_context["authorization"] = authorization
            if not got_from_cookie:
                cookies_to_set = "password=%s" % (authorization)
                request_context["headers"]["Set-Cookie"] = cookies_to_set
            return authorization
        else:
            request_context["headers"]["Location"] = "http://%s:%d/" % (
                request_context["app_context"]["bind_address"],
                request_context["app_context"]["bind_port"]
            )
            raise util.HTTPError(307, "Temporary Redirect")
