#!/usr/bin/python
import logging

import constants

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
            constants.CONTENT_LENGTH:0
        }
