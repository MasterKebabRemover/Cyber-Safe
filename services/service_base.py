#!/usr/bin/python
import constants

class ServiceBase(object):
    @staticmethod
    def name():
        return None

    def __init__(
        self,
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
        request_context["content_length"] = int(
            request_context["req_headers"].get(constants.CONTENT_LENGTH, "0")
        )

    def handle_content(
        self,
        request_context,
    ):
        return False

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
        result = request_context.get("response")
        if result is not None:
            del request_context["response"]
        return result

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
