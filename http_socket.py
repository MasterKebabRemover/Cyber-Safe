#!/usr/bin/python
import errno
import socket
import logging
import urlparse
import traceback
import importlib

import constants
import util
from services import service_base
from pollable import Pollable
from collable import Collable


class HttpSocket(Pollable, Collable):
    def __init__(
        self,
        socket,
        state,
        app_context,
        fd_dict,
        service_class=service_base.ServiceBase()
    ):
        self.request_context = {
            "code": 200,
            "status": "OK",
            "req_headers": {},
            "headers": {},
            "accounts": {},
            "content": "",
            "response": "",
            "recv_buffer": "",
            "send_buffer": "",
        }
        self.socket = socket
        self.request_context["state"] = state
        self.request_context["fd_dict"] = fd_dict
        self.request_context["app_context"] = app_context
        self.request_context["callable"] = self
        self.service_class = service_class
        for service in constants.MODULE_DICT[app_context["block_device"]]:
            importlib.import_module("services.%s" % service)

        self._state_machine = self._get_state_machine()
        self._current_state = constants.GET_FIRST_LINE
        # logging.debug("%d is making our state %d" % (hash(self), self._current_state))

    def _get_state_machine(
        self,
    ):
        return {
            constants.GET_FIRST_LINE: {
                "func": self._get_first_line,
                "next": constants.GET_HEADERS,
            },
            constants.GET_HEADERS: {
                "func": self._get_headers,
                "next": constants.GET_CONTENT,
            },
            constants.GET_CONTENT: {
                "func": self._get_content,
                "next": constants.SEND_STATUS_LINE,
            },
            constants.SEND_STATUS_LINE: {
                "func": self._send_status_line,
                "next": constants.SEND_HEADERS,
            },
            constants.SEND_HEADERS: {
                "func": self._send_headers,
                "next": constants.SEND_RESPONSE,
            },
            constants.SEND_RESPONSE: {
                "func": self._send_response,
                "next": constants.TERMINATE,
            },
            constants.TERMINATE: {
                "func": self._terminate,
                "next": None,
            },
        }

    def on_read(
        self,
    ):
        try:
            util.receive_buffer(self)
            # logging.debug(self.request_context["recv_buffer"])
        except Exception as e:
            code = 500
            if isinstance(e, util.HTTPError):
                code = e.code
            traceback.print_exc()
            self.on_error()
            util.add_status(self, code, e)

    def on_idle(
        self,
    ):
        call_again = None
        try:
            # logging.debug("%d is at state %d" % (hash(self), self._current_state))
            call_again = self._state_machine[self._current_state]["func"]()
        except Exception as e:
            code = 500
            if isinstance(e, util.HTTPError):
                code = e.code
            traceback.print_exc()
            self.on_error()
            util.add_status(self, code, e)
            self.request_context["response"] = e.message
            self.service_class = service_base.ServiceBase(self.request_context)
        if call_again is None:
            call_again = True
        return call_again

    def on_write(
        self,
    ):
        try:
            while self.request_context["send_buffer"]:
                # logging.debug(self.request_context["send_buffer"])
                self.request_context["send_buffer"] = self.request_context["send_buffer"][
                    self.socket.send(self.request_context["send_buffer"]):
                ]
        except socket.error as e:
            if e.errno == errno.EPIPE:
                self.request_context["send_buffer"] = ""  # to stop sending
        except Exception as e:
            traceback.print_exc()
            self.on_error
            self.service_class = service_base.ServiceBase(self.request_context)

    def on_error(
        self,
    ):
        self.request_context["state"] = constants.CLOSING

    def on_close(
        self,
    ):
        self.socket.shutdown(socket.SHUT_WR)
        pass

    def on_finish(
        self,
        block="",
        error=None,
    ):
        self.request_context["state"] = constants.ACTIVE
        self.request_context["block"] = block
        # logging.debug("BLOCK %s" % block)
        try:
            if error:
                raise RuntimeError(str(error))
            wake_up_function = self.request_context.get("wake_up_function")
            self.request_context["wake_up_function"] = None
            if wake_up_function:
                wake_up_function(self.request_context)
        except Exception as e:
            code = 500
            if isinstance(e, util.HTTPError):
                code = e.code
            traceback.print_exc()
            self.on_error()
            util.add_status(self, code, e)
            self.request_context["response"] = e.message
            self.service_class = service_base.ServiceBase(self.request_context)

    def fileno(self):
        return self.socket.fileno()

    def _get_first_line(
        self,
    ):
        req, self.request_context["recv_buffer"] = util.recv_line(
            self.request_context["recv_buffer"])
        if not req:  # means that async server has yet to receive a full line
            return False
        req_comps = req.split(" ", 2)
        # logging.debug(req)
        # logging.debug(req_comps)
        if len(req_comps) != 3:
            raise RuntimeError("Incomplete HTTP protocol")
        if req_comps[2] != constants.HTTP_SIGNATURE:
            raise RuntimeError("Not HTTP protocol")

        method, uri, signature = req_comps
        if method not in constants.SUPPORTED_METHODS:
            raise RuntimeError(
                "HTTP unsupported method '%s'" % method,
            )
        if not uri or uri[0] != '/' or '\\' in uri:
            raise RuntimeError("Invalid URI")

        self.request_context["uri"] = uri
        self.request_context["parsed"] = urlparse.urlparse(uri)

        logging.debug(
            "fd %d called method %s" % (
                self.fileno(),
                self.request_context["parsed"].path
            )
        )

        REGISTRY = {
            service.name(): service for service in service_base.ServiceBase.__subclasses__()
        }
        self.service_class = REGISTRY.get(
            self.request_context["parsed"].path,
            REGISTRY.get("*"),
        )(self.request_context)
        self._current_state = self._state_machine[self._current_state]["next"]
        self.service_class.before_request_headers(self.request_context)
        self.request_context["req_headers"] = self.service_class.get_header_dict(
        )

    def _get_headers(
        self,
    ):
        if util.get_headers(self.request_context):
            self.request_context["content_length"] = int(
                self.request_context["req_headers"].get(
                    constants.CONTENT_LENGTH, "0")
            )
            self._current_state = self._state_machine[self._current_state]["next"]
            self.service_class.before_request_content(self.request_context)
        else:
            return False

    def _get_content(
        self,
    ):
        service_command = None
        while True:
            service_command = self.service_class.handle_content(
                self.request_context)
            if service_command is not True:
                break

        if service_command is None:
            self.service_class.before_response_status(self.request_context)
            self._current_state = self._state_machine[self._current_state]["next"]
            return True
        elif service_command is False:
            return False

    def _send_status_line(
        self,
    ):
        self.request_context["send_buffer"] += ((
            "%s %s %s\r\n"
        ) % (
            constants.HTTP_SIGNATURE,
            self.request_context["code"],
            self.request_context["status"],
        )
        ).encode("utf-8")
        self.request_context["status_sent"] = True
        self.service_class.before_response_headers(self.request_context)
        self._current_state = self._state_machine[self._current_state]["next"]

    def _send_headers(
        self,
    ):
        if util.send_headers(self.request_context):
            self._current_state = self._state_machine[self._current_state]["next"]
        self.service_class.before_response_content(self.request_context)

    def _send_response(
        self,
    ):
        service_command = self.service_class.response(self.request_context)
        if self.request_context["response"]:
            self.request_context["send_buffer"] += self.request_context["response"]
            self.request_context["response"] = ""
        if service_command is None:
            service_command = constants.MOVE_TO_NEXT_STATE

        if service_command == constants.MOVE_TO_NEXT_STATE:
            self.service_class.before_terminate(self.request_context)
            self._current_state = self._state_machine[self._current_state]["next"]

        elif service_command == constants.RETURN_AND_WAIT:
            return False

        elif service_command == constants.CALL_SERVICE_AGAIN:
            return True

    def _terminate(
        self,
    ):
        self.service_class.before_terminate(self.request_context)
        self.request_context["state"] = constants.CLOSING
        return False

    def _reset_request_context(
        self,
    ):
        self.request_context["code"] = 200
        self.request_context["status"] = "OK"
        self.request_context["req_headers"] = {}
        self.request_context["response"] = ""
        self.request_context["headers"] = {}
