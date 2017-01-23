#!/usr/bin/python
import contextlib
import errno
import logging
import select
import socket
import traceback

import constants
import http_socket


class Server(object):
    _fd_dict = {}
    _terminate = False

    def __init__(
        self,
        log,
        event_object,
        bind_address,
        bind_port,
        timeout=100000,
        max_connections=10,
        max_buffer_size=1024*1024
    ):
        self._log = log
        self._event_object = event_object
        self._timeout = timeout
        self._bind_address = bind_address
        self._bind_port = bind_port
        self._max_connections = max_connections
        self._max_buffer_size = max_buffer_size

    def stop(self, signum, frame):
        self._terminate = True

    def _unregister(self, entry):
        logging.debug("Unregistered fd %s\n", entry.socket.fileno())
        self._event_object.unregister(entry.socket.fileno())
        del self._fd_dict[entry.socket.fileno()]
        entry.socket.close()

    def _recv_data(self, entry):
        free_buffer_size = self._max_buffer_size - len(
            entry.recv_buffer
        )
        data = ""
        try:
            while len(data) < free_buffer_size:
                buffer = entry.socket.recv(free_buffer_size - len(data))
                # logging.debug(buffer)
                if not buffer:
                    break
                data += buffer
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK:
                raise
        return data

    def _send_data(self, entry):
        try:
            while entry.send_buffer:
                # logging.debug(entry.send_buffer)
                entry.send_buffer = entry.send_buffer[
                    entry.socket.send(entry.send_buffer):
                ]
        except socket.error as e:
            if e.errno != errno.EWOULDBLOCK:
                raise

    def _get_new_connection(self, entry):
        try:
            client_entry = None
            client, c_address = entry.socket.accept()
            client_entry = http_socket.HttpSocket(
                    client,
                    constants.READING,
                )
            client.setblocking(0)
            logging.debug(
                "new connection: %s",
                client.fileno(),
            )
            self._fd_dict[client_entry.socket.fileno()] = client_entry
        except Exception:
            logging.error(traceback.format_exc())
            if client_entry:
                client_entry.socket.close()

    def run(self):
        with contextlib.closing(
            socket.socket(
                family=socket.AF_INET,
                type=socket.SOCK_STREAM,
            )
        )as server:
            self._fd_dict[server.fileno()] = http_socket.HttpSocket(
                server,
                constants.SERVER,
            )

            server.bind(
                (self._bind_address, self._bind_port)
            )
            server.listen(
                self._max_connections
            )
            logging.debug("HTTP server running")

            while self._fd_dict:
                try:
                    if self._terminate:
                        logging.debug("Terminating")
                        self._terminate = False
                        for entry in self._fd_dict.values():
                            entry.state = constants.CLOSING

                    for entry in self._fd_dict.values():
                        if entry.state == constants.CLOSING and (
                                entry.state == constants.SERVER or
                                not entry.send_buffer):
                                    self._unregister(entry)

                    for entry in self._fd_dict.values():
                        while entry.on_receive():
                            pass

                    for entry in self._fd_dict.values():
                        mask = select.POLLERR
                        if entry.send_buffer:
                            mask |= select.POLLOUT
                        if entry.state == constants.SERVER or len(
                            entry.recv_buffer
                        ) < self._max_buffer_size:
                            mask |= select.POLLIN
                        self._event_object.register(
                            entry.socket.fileno(), mask
                        )

                    events = ()
                    try:
                        events = self._event_object.poll(self._timeout)
                    except select.error as e:
                        if e[0] != errno.EINTR:
                            raise
                    for fd, flag in events:
                        entry = self._fd_dict[fd]
                        try:
                            if flag & (select.POLLHUP | select.POLLERR):
                                raise RuntimeError(
                                    "socket hung up or experienced error"
                                )

                            if flag & select.POLLIN:
                                if entry.state == constants.SERVER:
                                    self._get_new_connection(
                                        entry,
                                    )
                                else:
                                    data = self._recv_data(entry)
                                    if not data:
                                        raise RuntimeError("Disconnect")
                                    entry.recv_buffer += data
                                    while entry.on_receive():
                                        pass

                            if flag & select.POLLOUT:
                                self._send_data(entry)

                        except Exception as e:
                            logging.error(traceback.format_exc())
                            self._unregister(entry)
                except Exception as e:
                    logging.error(traceback.format_exc())
                    self._terminate = True

        logging.debug("server terminated\n")
