"""Mooltipy - a python library for the Mooltipass

Mostly ripped out of mooltipas_coms.py from the mooltipass project (relative
path /tools/python_comms/mooltipass_coms.py). This is my learning guide with
a goal of creating a non-browser mooltipas management utility.

If you are having difficulty with core stuff (e.g. establishing a connection
to the mooltipass) it may be wise to compare with that file as I have trimmed
things down for simplicity.

Classes:
    Mooltipass -- Encapsulates access to a Mooltipass on your system

"""

from array import array

import logging
import platform
import random
import sys
import time

import usb.core

from .constants import *


class Mooltipass(object):
    """"""

    _CMD_INDEX = 0x01
    _DATA_INDEX = 0x02

    _epin = None
    _epout = None
    _hid_device = None

    _intf = None

    def __init__(self):
        """Create object representing a Mooltipass.

        Raises RuntimeError on failure.
        """

        USB_VID = 0x16D0
        USB_PID = 0x09A0

        # Find the device
        self._hid_device = usb.core.find(idVendor=USB_VID, idProduct=USB_PID)

        if self._hid_device is None:
            raise RuntimeError('Mooltipass not found')

        # Different init codes depending on the platform
        if platform.system() == "Linux":
            try:
                self._hid_device.detach_kernel_driver(0)
                self._hid_device.reset()
            except Exception, e:
                pass # Probably already detached
        else:
            # Set the active configuration. With no arguments, the first configuration will be the active one
            try:
                self._hid_device.set_configuration()
            except Exception, e:
                raise RuntimeError('Cannot set device configuration: ' + str(e))

        # Get an endpoint instance
        cfg = self._hid_device.get_active_configuration()
        self._intf = cfg[(0,0)]

        # Match the first OUT endpoint
        self._epout = usb.util.find_descriptor(
                self._intf,
                custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        if self._epout is None:
            self._hid_device.reset()
            raise RuntimeError("Couldn't match the first OUT endpoint?")

        # Match the first IN endpoint
        self._epin = usb.util.find_descriptor(
                self._intf,
                custom_match = lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)
        if self._epin is None:
            self._hid_device.reset()
            raise RuntimeError("Couldn't match the first IN endpoint?")

    @staticmethod
    def _tf_return(recv):
        """Return True or False based on typical command response."""
        DATA_INDEX = 2
        return (lambda recv: False if recv[DATA_INDEX] == 0 else True)(recv)

    def send_packet(self, cmd, data):
        """Sends a packet to our mooltipass.

        Keyword arguments:
            cmd -- command to send
            data -- array [or struct?]
        """

        data_len = 0
        if data is not None:
            data_len = len(data)


        # Data sent over to the generic HID should be in 64 byte packets and in
        # the following array structure:
        #   buffer[0]  = length of data
        #   buffer[1]  = command identifier for this packet
        #   buffer[2:] = packet data
        arraytosend = array('B')
        arraytosend.append(data_len)
        arraytosend.append(cmd)

        ##### Original code only appended command if it wasn't 0???
        ##### What is CMD 0 used for then, straight data transfer?

        if data is not None:
            arraytosend.extend(data)

        self._epout.write(arraytosend)

    def recv_packet(self, timeout=5000):
        """Receives a packet from the mooltipass.

        Keyword arguments:
            timeout -- how long to wait for user to complete entering pin
                    (default 20000).
        """
        recv = None
        # The mooltipass should reply with 0xB9 if the user is currently
        # entering hs PIN, but I don't see this behavior
        while True:
            recv = self._epin.read(self._epin.wMaxPacketSize, timeout=timeout)
            if recv is not None and recv[self._DATA_INDEX] != 0xB9:
                break
            print(recv)
            time.sleep(.5)
        return recv

    def ping(self):
        """Ping the mooltipass (0xA1)

        Ping the mooltipass and return true/false on success/failure.
        """
        try:
            send_data = array('B')
            send_data.append(random.randint(0,255))
            send_data.append(random.randint(0,255))

            self.send_packet(CMD_PING, send_data)

            recv = None
            while recv is None or \
                    recv[self._DATA_INDEX] != send_data[0] or \
                    recv[self._DATA_INDEX+1] != send_data[1]:

                recv = self.recv_packet()

            logging.info("Mooltipass replied to our ping message")
            return True

        except usb.core.USBError as e:
            logging.error(e)
            return False

    def get_version(self):
        """Get mooltipass firmware version. (0xA2)"""
        #TODO: Figure out how to read the string version number?
        self.send_packet(CMD_VERSION, None)
        return self.recv_packet()

    def set_context(self, context):
        """Set mooltipass context. (0xA3)

        Returns True if successful, False if context is unknown and
        None if no card is in the mooltipass.
        """

        self.send_packet(CMD_CONTEXT, array('B', context + b'\x00'))
        recv = self.recv_packet(10000)
        if recv[self._DATA_INDEX] == 0:
            return False
        if recv[self._DATA_INDEX] == 1:
            return True
        if recv[self._DATA_INDEX] == 3:
            return None

    def get_login(self):
        """Get the login for current context. (0xA4)"""
        logging.info('Not yet implemented')
        pass

    def get_password(self):
        """Get the password for current context. (0xA5)"""
        logging.info('Not yet implemented')
        pass

    def set_login(self, login):
        """Set a login. (0xA6)"""
        self.send_packet(CMD_SET_LOGIN, array('B', login + b'\x00'))
        return self._tf_return(self.recv_packet())

    def set_password(self, password):
        """Set a password for current context. (0xA7)"""
        self.send_packet(CMD_SET_PASSWORD, array('B', password + b'\x00'))
        return self._tf_return(self.recv_packet())

    def check_password(self, password):
        """Compare given password to set password for context. (0xA8)

        Call check_password() to avoid calling set_password() and 
        prompting the user to overwrite a value that already exists.
        """
        logging.info('Not yet implemented')
        pass

    def add_context(self, context):
        """Add a context. (0xA9)"""
        self.send_packet(CMD_ADD_CONTEXT, array('B', context + b'\x00'))
        return self._tf_return(self.recv_packet())

    def set_bootloader_password(self, password):
        """??? (0xAA)"""
        logging.info('Not yet implemented')
        pass

    def jump_to_bootloader(self):
        """??? (0xAB)"""
        logging.info('Not yet implemented')
        pass

    def get_random_number(self):
        """Get 32 random bytes. (0xAC)"""
        logging.info('Not yet implemented')
        pass

    def start_memory_management(self, timeout=20000):
        """Enter memory management mode. (0xAD)

        Keyword argument:
            timeout -- how long to wait for user to complete entering pin 
                    (default 20000).

            Note: Mooltipass times out after ~17.5 seconds of inaction
                    inaction.
        """

        # Memory management mode can only be accessed if the unit is unlocked.
        if not self.get_status() == 0x05:
            raise RuntimeError('Cannot enter memory management mode; ' + \
                    'mooltipass not unlocked.')

        self.send_packet(CMD_START_MEMORYMGMT, None)
        return self._tf_return(self.recv_packet())

    # ... lots of commands ...

    def end_memory_management(self):
        """End memory management mode. (0xD3)"""
        self.send_packet(CMD_END_MEMORYMGMT, None)
        return self._tf_return(self.recv_packet())

    # TODO: Make a status property and this function private
    def get_status(self):
        """Return raw mooltipass status as int. (0xB9)"""
        self.send_packet(CMD_MOOLTIPASS_STATUS, None)
        return self.recv_packet()[self._DATA_INDEX]
