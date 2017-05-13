#!/usr/bin/python
import contextlib
import collections
import errno
import logging
import select
import socket
import traceback

import constants
import http_socket
from tcp_listener import TCPListener


class Server(object):
    _fd_dict = {}
    _terminate = False

    def __init__(
        self,
        app_context,
    ):
        self._event_object = app_context["event_object"]
        self._timeout = app_context["timeout"]
        self._app_context = app_context

    def add_listener(
        self,
        bind_address,
        bind_port,
        initiate,
    ):
        listener = TCPListener(
            bind_address,
            bind_port,
            initiate,
            app_context=self._app_context,
            fd_dict=self._fd_dict,
        )
        self._fd_dict[listener.fileno()] = listener
        
    def stop(self, signum, frame):
        self._terminate = True

    def _unregister(self, entry):
        logging.debug("Unregistered fd %s\n", entry.fileno())
        del self._fd_dict[entry.fileno()]
        entry.on_close()
        entry.request_context["state"] = constants.CLOSING

    def _get_new_connection(self, entry):
        try:
            client_entry = None
            client, c_address = entry.socket.accept()
            client_entry = http_socket.HttpSocket(
                    client,
                    constants.READING,
                    self._app_context,
                )
            client.setblocking(0)
            logging.debug(
                "new connection: %s",
                client.fileno(),
            )
            self._fd_dict[client_entry.fileno()] = client_entry
            self._event_object.register(client.fileno(), 0)
        except Exception:
            logging.error(traceback.format_exc())
            if client_entry:
                client_entry.socket.close()

    def terminate(self):
        logging.debug("Terminating")
        self._terminate = False
        for entry in self._fd_dict.values():
            entry.request_context["state"] = constants.CLOSING

    def create_poller(self):
        poller = self._event_object()
        for entry in self._fd_dict.values():
            if entry.request_context["state"] == constants.SLEEPING:
                continue
            mask = select.POLLERR
            if (
                entry.request_context["send_buffer"]
            ):
                mask |= select.POLLOUT
            if (
                entry.request_context["state"] == constants.LISTENER or
                (
                    entry.request_context["state"] ==constants.ACTIVE and
                    len(entry.request_context["recv_buffer"]) < constants.BLOCK_SIZE
                )
            ):
                mask |= select.POLLIN
            poller.register(
                entry.fileno(), mask
            )
        return poller

    def run(self):
        logging.debug("HTTP server running")
        while self._fd_dict:
            try:
                if self._terminate:
                    self.terminate()

                for entry in self._fd_dict.values():
                    if (
                            entry.request_context["state"] == constants.CLOSING and
                            not entry.request_context["send_buffer"]
                        ):
                            self._unregister(entry)

                for entry in self._fd_dict.values():
                    try:
                        # logging.debug(entry)
                        while entry.request_context["state"] != constants.SLEEPING and entry.on_idle():
                            pass
                    except Exception as e:
                        logging.error(traceback.format_exc())
                        self._unregister(entry)
                events = ()
                try:
                    for fd, flag in self.create_poller().poll(self._timeout):
                        entry = self._fd_dict[fd]
                        try:
                            if flag & (select.POLLHUP | select.POLLERR):
                                raise RuntimeError(
                                    "socket hung up or experienced error"
                                )
                            if flag & select.POLLIN:
                                entry.on_read()
                            if flag & select.POLLOUT:
                                entry.on_write()
                        except Exception as e:
                            logging.error(traceback.format_exc())
                            self._unregister(entry)
                except select.error as e:
                    if e[0] != errno.EINTR:
                        raise
            except Exception as e:
                logging.error(traceback.format_exc())
                self._terminate = True
        logging.debug("server terminated\n")
