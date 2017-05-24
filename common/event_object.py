## @package cyber-safe.common.events_object
# Asynchronous I/O event handler.
#
import select

## Event base object.
class EventBase(object):
    ## Constructor.
    def __init__(self):
        pass

    ## Class name.
    # @returns (str) class name
    #
    @staticmethod
    def name():
        return None

    ## Registers a socket with a mask into the event object.
    #
    # @param fd (int) file descriptor of socket.
    # @param mask (int) event mask of socket.
    #
    def register(self, fd, mask):
        pass

    ## Unregisters a socket from the event object
    def unregister(self, fd):
        pass

    ## Returns the poll result of the event object
    #   
    #   @param timeout (int) poll timeout.
    #
    def poll(self, timeout):
        raise NotImplementedError()

## Poll events object.
#
# Uses select.poll() for event handling.
#
class PollEvents(EventBase):
    ## Constructor.
    def __init__(self):
        super(PollEvents, self).__init__()
        self._poll_object = select.poll()

    ## Class name.
    # @returns (str) class name
    #
    @staticmethod
    def name():
        return "poll"

    ## Registers a socket with a mask into the event object.
    #
    # @param fd (int) file descriptor of socket.
    # @param mask (int) event mask of socket.
    #
    def register(self, fd, mask):
        self._poll_object.register(fd, mask)

    ## Unregisters a socket from the event object
    def unregister(self, fd):
        self._poll_object.unregister(fd)

    ## Returns the poll result of the event object
    #   
    #   @param timeout (int) poll timeout.
    #   @returns poll object
    #
    def poll(self, timeout):
        return self._poll_object.poll(timeout)

## Select events object.
#
# Wraps the select functions to be used as poll functions, with same inputs and outputs.
#
class SelectEvents(EventBase):
    ## Constructor.
    def __init__(self):
        self._fd_dict = {}
        super(SelectEvents, self).__init__()

    ## Class name.
    # @returns (str) class name
    #
    @staticmethod
    def name():
        return "select"

    ## Registers a socket with a mask into the event object.
    #
    # @param fd (int) file descriptor of socket.
    # @param mask (int) event mask of socket.
    #
    def register(self, fd, mask):
        self._fd_dict[fd] = mask

    ## Unregisters a socket from the event object
    def unregister(self, fd):
        del self._fd_dict[fd]

    ## Returns the poll result of the event object
    #   
    #   @param timeout (int) poll timeout.
    #   @returns poll object
    #
    def poll(self, timeout):
        events_dict = {}
        rlist, wlist, xlist = [], [], []
        mask_to_list = {
            select.POLLERR: xlist,
            select.POLLOUT: wlist,
            select.POLLIN: rlist,
        }

        for fd, mask in self._fd_dict.items():
            for select_mask in mask_to_list.keys():
                if fd not in mask_to_list[select_mask]:
                    if mask & select_mask:
                        mask_to_list[select_mask].append(fd)
                events_dict[fd] = 0

        r_ready, w_ready, x_ready = select.select(rlist, wlist, xlist, timeout)
        select_to_poll = {
            tuple(w_ready): select.POLLOUT,
            tuple(r_ready): select.POLLIN,
            tuple(x_ready): select.POLLERR,
        }
        for ready_list in select_to_poll.keys():
            for fd in ready_list:
                events_dict[fd] |= select_to_poll[ready_list]
        return events_dict.items()
