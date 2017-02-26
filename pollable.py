#!/usr/bin/python
import abc

class Pollable(object):
    __metaclass__ = abc.ABCMeta
    send_buffer = ""
    recv_buffer = ""

    @abc.abstractmethod
    def on_read(self):
        return

    @abc.abstractmethod
    def on_write(self):
        return

    @abc.abstractmethod
    def on_error(self):
        return

    @abc.abstractmethod
    def on_close(self):
        return

    @abc.abstractmethod
    def fileno(self):
        return

    def on_receive(self):
        return