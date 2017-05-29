## @package common.utilities.block_util
#
# Various block handling utilities.
## @file block_util.py Implementation of @ref common.utilities.block_util
import errno
import socket
from common import constants
from common.utilities import util
from common.utilities import integration_util
from common.utilities import encryption_util
import logging

## Perform action (read/write) with block.
# @param request_context (dict) sender request context.
# @param block_num (int) index of wanted block.
# @param action (str) indicates action type (read/write).
# @param service_wake_up (function) function that is called when action ends.
# @param block (str) block to write.
#
# According to parameters, updates request context and calls lower function.
#
def bd_action(
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

## Read block from devices.
# @param request_context (dict) requst context.
#
# Initializes cliens to read splitted blocks from block devices.
# For every block part received, adds it to constructed block.
# When all parts received, decrypts block with frontend key and wakes up service with block.
#
def read_block(
    request_context,
):
    if request_context.get("read_block") is None:
        request_context["read_block"] = bytearray(constants.BLOCK_SIZE)
        request_context["replies"] = 0
        request_context["wake_up_function"] = read_block
        request_context["state"] = constants.SLEEPING
        for d in request_context["app_context"]["devices"]:
            init_client(
                request_context,
                constants.READ,
                request_context["block_num"],
                block_device_id=d,
            )

    else:
        request_context["replies"] += 1
        request_context["read_block"] = integration_util.decrypt_data([
            request_context["read_block"],
            request_context["block"],
        ]
        )
        if request_context.get("replies") == len(
                request_context["app_context"]["devices"]):
            request_context["app_context"]["semaphore"].release()
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
            request_context["block"] = request_context["read_block"]
            request_context["read_block"] = None
            request_context["service_wake_up"](request_context)
        else:
            request_context["state"] = constants.SLEEPING
            request_context["wake_up_function"] = read_block

## Write block to devices.
# @param request_context (dict) requst context.
# @param block (str) block data to write.
#
# Encrypts block with frontend key, then splits to multiple parts.
# Initializes cliens to write splitted parts to block devices.
#
def write_block(
    request_context,
    block,
):
    aes = encryption_util.get_aes(
        key=request_context["app_context"]["config"].get('frontend', 'key'),
        ivkey=request_context["app_context"]["config"].get(
            'frontend', 'ivkey'),
        block_num=request_context["block_num"],
    )
    block = encryption_util.encrypt_block_aes(aes, block)
    block_list = integration_util.encrypt_data(block, len(request_context["app_context"]["devices"]))
    for i in range(len(request_context["app_context"]["devices"])):
        init_client(
            request_context=request_context,
            client_action=constants.WRITE,
            client_block_num=request_context["block_num"],
            block=block_list[i],
            block_device_id=request_context["app_context"]["devices"].keys()[
                i],
        )
    while request_context["app_context"]["semaphore"].get_value(
    ) < constants.MAX_SEMAPHORE:
        request_context["app_context"]["semaphore"].release()

## Initialize client function.
# @param request_context (dict) request context.
# @param client_action (str) whether client should read/write.
# @param client_block_num (int) block index to preform action with.
# @param block_device_id (str) block device with which client should interact.
# @param block (str) block data in case of write.
#
# creates a pollable client object.
# connects client socket to block device.
# adds client to asynchronous poller.
# 
def init_client(
    request_context,
    client_action,
    client_block_num,
    block_device_id,
    block=None,
):
    from common.pollables.http_client import HttpClient
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    devices = request_context["app_context"]["devices"]
    request_context["user_to_send"] = devices[block_device_id]["username"]
    request_context["password_to_send"] = devices[block_device_id]["password"]
    client = HttpClient(
        socket=s,
        state=constants.ACTIVE,
        app_context=request_context["app_context"],
        fd_dict=request_context["fd_dict"],
        action=client_action,
        block_num=client_block_num,
        parent=request_context["callable"],
        block=block,
    )
    try:
        s.connect(
            (devices[block_device_id]["address"],
             devices[block_device_id]["port"],
             ))
        s.setblocking(False)
    except Exception as e:
        if e.errno != errno.ECONNREFUSED:
            raise
        raise util.HTTPError(500, "Internal Error", "Block Device not found")
    request_context["fd_dict"][client.fileno()] = client
