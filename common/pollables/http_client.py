
import errno
import socket
import logging
import traceback
import importlib

from client.services import *
from common import constants
from common.utilities import util
from common.services import service_base
from common.pollables.pollable import Pollable

class HttpClient(Pollable):
    def __init__(
        self,
        socket,
        state,
        app_context,
        fd_dict,
        action,  # must be constants.READ or constants.WRITE
        block_num,
        parent,
        block=None
    ):
        self.request_context = {
            "code": None,
            "status": None,
            "req_headers": {},
            "headers": {},
            "content": "",
            "response": "",
            "recv_buffer": "",
            "send_buffer": "",
        }
        self.socket = socket
        self.request_context["state"] = state
        self._fd_dict = fd_dict
        self.request_context["app_context"] = app_context
        self.service_class = service_base.ServiceBase(self.request_context)
        self.request_context["action"] = action
        self.request_context["block_num"] = block_num
        self.request_context["parent"] = parent
        self.request_context["block"] = block

        REGISTRY = {
            service.name(): service for service in service_base.ServiceBase.__subclasses__()
        }

        try:
            self.service_class = REGISTRY[action](self.request_context)
        except KeyError:
            raise util.HTTPError(
                code=500,
                status="Internal Error",
                message="service not supported",
            )
        self._state_machine = self._get_state_machine()
        self._current_state = constants.SEND_STATUS_LINE

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
                "next": constants.TERMINATE,
            },
            constants.TERMINATE: {
                "func": self._terminate,
                "next": None
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
                "next": constants.GET_FIRST_LINE,
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
            self.on_error(e)
            util.add_status(self, code, e)
        self.on_idle()

    def on_idle(
        self,
    ):
        # logging.debug("HASH: %d STATE: %d" % (hash(self), self._current_state))
        call_again = None
        try:
            call_again = self._state_machine[self._current_state]["func"]()
        except Exception as e:
            code = 500
            if isinstance(e, util.HTTPError):
                code = e.code
            traceback.print_exc()
            self.on_error(e)
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
                # logging.debug(hash(self))
                # logging.debug(self.request_context["send_buffer"])
                self.request_context["send_buffer"] = self.request_context["send_buffer"][
                    self.socket.send(self.request_context["send_buffer"]):
                ]
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK:
                raise

    def on_error(
        self,
        error=None,
    ):
        if error:
            self.request_context["parent"].on_finish(error=error)
        self.request_context["state"] = constants.CLOSING

    def on_close(
        self,
    ):
        self.socket.shutdown(socket.SHUT_RD)

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
        if req_comps[0] != constants.HTTP_SIGNATURE:
            raise RuntimeError("Not HTTP protocol")

        if req_comps[1] != "200":
            raise util.HTTPError(
                req_comps[1],
                req_comps[2],
                message="",
            )
        self._current_state = self._state_machine[self._current_state]["next"]
        self.service_class.before_request_headers(self.request_context)

    def _get_headers(
        self,
    ):
        if util.get_headers(self.request_context):
            self.request_context["content_length"] = int(
                self.request_context["req_headers"].get(
                    constants.CONTENT_LENGTH, "0")
            )
            self.service_class.before_request_content(self.request_context)
            self._current_state = self._state_machine[self._current_state]["next"]

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
        self.request_context["req_headers"] = self.service_class.get_header_dict(
        )
        self.service_class.before_response_status(self.request_context)
        self._current_state = self._state_machine[self._current_state]["next"]

    def _send_headers(
        self,
    ):
        self.service_class.before_response_headers(self.request_context)
        if util.send_headers(self.request_context):
            self._current_state = self._state_machine[self._current_state]["next"]
            self.service_class.before_response_content(self.request_context)

    def _send_response(
        self,
    ):
        data = None
        data = self.service_class.response(self.request_context)
        if data is None:
            self._current_state = self._state_machine[self._current_state]["next"]
        else:
            self.request_context["send_buffer"] += data
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
