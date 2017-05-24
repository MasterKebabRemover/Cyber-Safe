import socket
from common import constants
from common.utilities import util
from common.utilities import integration_util
from common.utilities import encryption_util
import logging


def bd_action(  # should be called instead of read_block, write_block
    request_context,
    block_num,
    action,
    service_wake_up=None,
    block=None
):
    request_context["block_num"] = block_num
    if action == constants.READ:
        if not request_context["app_context"]["semaphore"].acquire(False):
            raise RuntimeError('Disk busy')
        request_context["service_wake_up"] = service_wake_up
        request_context["read_block"] = None
        read_block(request_context)
    elif action == constants.WRITE:
        if request_context["app_context"]["semaphore"].get_value() == 0:
            raise RuntimeError('Disk busy')
        while request_context["app_context"]["semaphore"].acquire(False):
            pass
        write_block(request_context, block)
    else:
        raise RuntimeError('Invalid action')


def read_block(
    request_context,
):
    if request_context.get("read_block") is None:
        # initialize
        request_context["read_block"] = bytearray(constants.BLOCK_SIZE)
        request_context["replies"] = 0
        request_context["wake_up_function"] = read_block
        request_context["state"] = constants.SLEEPING
        for d in request_context["app_context"]["devices"]:
            init_client(
                request_context,
                constants.READ,
                request_context["block_num"],
                block_device_num=d,
            )

    else:
        request_context["replies"] += 1
        request_context["read_block"] = integration_util.decrypt_data(
            request_context["read_block"],
            request_context["block"],
        )
        # if received all replies, decrypt wake up the service back
        if request_context.get("replies") == len(
                request_context["app_context"]["devices"]):
            request_context["app_context"]["semaphore"].release()
            # decrypt data with aes frontend key
            aes = encryption_util.get_aes(
                key=request_context["app_context"]["config"].get(
                    'frontend', 'key'),
                ivkey=request_context["app_context"]["config"].get(
                    'frontend', 'ivkey'),
                block_num=request_context["block_num"],
            )
            request_context["read_block"] = encryption_util.decrypt_block_aes(
                aes,
                request_context["read_block"],
            )
            # pass data to service
            request_context["block"] = request_context["read_block"]
            request_context["read_block"] = None
            request_context["service_wake_up"](request_context)
        else:
            request_context["state"] = constants.SLEEPING
            request_context["wake_up_function"] = read_block


def write_block(
    request_context,
    block,
):
    # encrypt using aes and frontend keys
    aes = encryption_util.get_aes(
        key=request_context["app_context"]["config"].get('frontend', 'key'),
        ivkey=request_context["app_context"]["config"].get(
            'frontend', 'ivkey'),
        block_num=request_context["block_num"],
    )
    block = encryption_util.encrypt_block_aes(aes, block)
    # encrypt using byte split method
    block = integration_util.encrypt_data(block)
    # send data to all block devices
    for i in range(len(request_context["app_context"]["devices"])):
        init_client(
            request_context=request_context,
            client_action=constants.WRITE,
            client_block_num=request_context["block_num"],
            block=block[i],
            block_device_num=request_context["app_context"]["devices"].keys()[
                i],
        )
    while request_context["app_context"]["semaphore"].get_value(
    ) < constants.MAX_SEMAPHORE:
        request_context["app_context"]["semaphore"].release()

def init_client(
    request_context,
    client_action,
    client_block_num,
    block_device_num,
    block=None,
):
    from common.pollables.http_client import HttpClient
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    config = request_context["app_context"]["config"]
    request_context["user_to_send"] = config.get("blockdevice.%d" % block_device_num, "username")
    request_context["password_to_send"] = config.get("blockdevice.%d" % block_device_num, "password")
    client = HttpClient(
        socket=s,
        state=constants.ACTIVE,
        app_context=request_context["app_context"],
        fd_dict=request_context["fd_dict"],
        action=client_action,  # must be constants.READ or constants.WRITE
        block_num=client_block_num,  # this is directory root
        parent=request_context["callable"],
        block=block,
    )
    try:
        s.connect(
            (request_context["app_context"]["devices"][block_device_num]["address"],
             request_context["app_context"]["devices"][block_device_num]["port"],
             ))
        s.setblocking(False)
    except Exception as e:
        if e.errno != errno.ECONNREFUSED:
            raise
        raise HTTPError(500, "Internal Error", "Block Device not found")
    request_context["fd_dict"][client.fileno()] = client
