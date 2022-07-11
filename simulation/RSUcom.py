import select
import socket
from typing import List, Tuple

HOSTADDR = ('127.0.0.1', 2013)  # IP-address of this machine
FROMRSUADDR = ('127.0.0.1', 5000)  # Internal address
TORSUADDR = ('127.0.0.1', 5001)  # Internal address
CCADDR = ('127.0.0.1', 2000)  # Address of CC
TIMEOUT = 0.1  # timeout value in seconds for receiving

LEN = 18  # Length of a message array in the model.

# Lengths of received messages for OS
MESSAGELENGTHS = {
    0x00: 2,
    0x20: 5,
    0x60: 92,
    0x61: 92,
    0x62: 3,
    0x63: 6,
    0x64: 6,
    0x65: 3,
    0x66: 3,
    0x68: 2,
    0x69: 3,
    0x80: 2,
    0x81: 2,
    0x82: 2,
    0x83: 2,
    0x84: 2,
    0x85: 2,
    0x86: 2,
    0x87: 2,
    0x88: 4,
    0x89: 2,
    0x8a: 2,
    0x8b: 2,
    0xA0: 2,
    0xA1: 2,
    0xA2: 2,
    0xA3: 2,
    0xA4: 2,
    0xA5: 2,
    0xA6: 2,
    0xA8: 2,
    0xA9: 2
}


def decodeMessageBlock(data: bytes) -> Tuple[List[int], List[bytes]]:
    """ Receive and decode a message block from the CC. Does not handle timeouts.

    :param data: The message block that was received.
    :return: A list of acknowledgements and a list of messages that were received.
    """
    assert len(data) == data[0]
    if data[1] != 1 or data[2] != 3:
        print('Unexpected protocol version %d.%d' % (data[1], data[2]))
    nmsg = data[3]
    nack = data[4]
    data = data[5:]
    acks = []
    msgs = []
    for ack in range(nack):
        print('Acknowledged %d' % data[ack])
        acks.append(data[ack])
    data = data[nack:]

    for _ in range(nmsg):
        msgType = data[1]
        length = MESSAGELENGTHS[msgType]
        msgs.append(data[0:length])
        data = data[length:]
    return acks, msgs


class RSUSocket:
    def __init__(self):
        # Internal socket to receive messages from RSU-sim
        self.fromRSU = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fromRSU.bind(FROMRSUADDR)

        # Internal socket to send messages to RSU-sim (after request)
        self.toRSU = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.toRSU.bind(TORSUADDR)

        # External socket for all CC communication
        self.CC = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.CC.bind(HOSTADDR)

        # Messages that are 'in transit' to CC
        self.buffer = []
        # Messages that were received by CC
        self.acks = []
        # Default message index
        self.i = 1

        assert LEN > 5, 'Message buffer too short.'
        assert LEN <= 32, 'Message buffer too large for "Verzoek snelheid laatste voertuig"'
        assert LEN <= 72, 'Message buffer too large for MSI status'
        assert LEN <= 90, 'Message buffer too large for legend commands'
        assert LEN <= 91, 'Message buffer too large for legend request'
        assert LEN <= 96, 'Message buffer too large for "Verzoek snelheid en intensiteit"'

    def encodeMessageBlock(self, acks: List[int], messages: List[bytes], i=-1) -> bytes:
        """ Encode acknowledges and messages into a message block.

        :param acks: List of up to 15 acknowledgements (message IDs)
        :param messages: List of up to 15 messages (properly formatted, without message ID prefixed
        :param i: Optional argument to specify ID of first message, leave blank to continue from last value
        :return: A single message block
        """
        assert len(acks) <= 15
        assert len(messages) <= 15
        block = bytes([1, 3, len(messages), len(acks)])
        for ack in acks:
            block += bytes([ack])
        if i > 0:
            self.i = i
        for d in messages:
            block += bytes([self.i]) + d
            self.i = (self.i + 1) % 256
        assert len(block) <= 254  # block including length byte should be at most 255
        block = bytes([len(block) + 1]) + block
        return block

    def send(self, data: bytes):
        """ Send a message to the CC.
        Low-level send function

        :param data: the message to send
        """
        self.CC.sendto(data, CCADDR)
        print("sent %s to %s:%d" % (data.hex(' '), CCADDR[0], CCADDR[1]))

    def recv(self) -> bytes:
        """ Receive a message from the RSU.
        Low-level send function, does not handle timeouts.

        :return: the message that was received
        """
        data, addr = self.CC.recvfrom(256)
        print("received %s from %s:%d" % (data.hex(' '), addr[0], addr[1]))
        return data

    def sendMessageBlock(self, acks: List[int], messages: List[bytes], i=-1):
        """ Encode and send a message block to the CC. Does not handle timeouts.

        :param acks: List of up to 15 acknowledgements (message IDs)
        :param messages: List of up to 15 messages (properly formatted, without message ID prefixed
        :param i: Optional argument to specify ID of first message, leave blank to continue from last value
        """
        block = self.encodeMessageBlock(acks, messages, i=i)
        self.send(block)

    def recvMessageBlock(self) -> Tuple[List[int], List[bytes]]:
        """ Receive and decode a message block from the RSU. Does not handle timeouts.

        :return: A list of acknowledgements and a list of messages that were received.
        """
        data = self.recv()
        return decodeMessageBlock(data)

    def mainLoop(self) -> None:
        # Select returns a list of ports that have data present.
        # After TIMEOUT seconds, returns an empty list if no ports have data.
        recvPorts, _, _ = select.select([self.CC, self.toRSU, self.fromRSU], [], [], TIMEOUT)

        # RSU requests data from CC
        if self.toRSU in recvPorts:
            (data, addr) = self.toRSU.recvfrom(255)
            if self.buffer:
                # take the first message from the buffer and prepare an acknowledgement for sending.
                # byte 1 is prefixed to signal a message was received
                data = bytes([1]) + self.buffer.pop(0)
                nack = len(self.acks)
                if nack < 15:
                    data += bytes([nack]) + bytes(self.acks) + bytes(15 - nack)
                    self.acks = []
                else:
                    data += bytes([15] + self.acks[:15])
                    self.acks = self.acks[15:]
            else:
                # return a bytelist of all 0's
                data = bytes(LEN + 3)
            self.toRSU.sendto(data, addr)

        # RSU sent data to CC
        if self.fromRSU in recvPorts:
            message = self.fromRSU.recv(255)
            fc = message[1] // 32
            sfc = message[1] % 32
            if fc == 0 or fc == 1:
                print('Unsupported message from RSU.')
                # note that CC is not received if this happens
                return
            elif fc == 3:  # command copy
                if sfc in [0, 1]:  # OPA, AID legend
                    print('Legend command')
                    data = message + bytes(91 - LEN)
                elif sfc in [2, 5, 6, 9]:  # RSU state, brightness, MUS state, speed
                    print('Single value command')
                    data = message[0:3]
                elif sfc in [3, 4]:  # detector state (2x)
                    print('Detector state command')
                    data = message[0:6]
                elif sfc in [8]:  # MUS test
                    print('MUS test command')
                    data = message[0:2]
                else:
                    print('Unknown sfc: %d in %s' % (sfc, message.hex(' ')))
                    # note that CC is not received if this happens
                    return
            elif fc == 2 or fc == 4:  # data
                if sfc == 0:
                    print('Unsupported: (autonomous) data MSI legend states')
                    # note that CS is not received if this happens
                    return
                elif sfc == 1:
                    print('(autonomous) data MSI states')
                    data = message + bytes(72 - LEN)
                elif sfc == 2:
                    print('(autonomous) data MSI legends')
                    data = message + bytes(91 - LEN)
                elif sfc == 3:
                    print('(autonomous) data MUS state')
                    data = message[0:4]
                elif sfc == 4:
                    print('(autonomous) data detector states')
                    data = message + bytes(32 - LEN)
                elif sfc == 5:
                    print('(autonomous) data RSU status')
                    data = message[0:4]
                elif sfc == 6:
                    print('(autonomous) data minute speeds')
                    data = message + bytes(96 - LEN)
                elif sfc == 7:
                    print('(autonomous) data last speed')
                    data = message + bytes(32 - LEN)
                elif sfc == 8:
                    print('(autonomous) data version numbers')
                    data = message[0:6]
                elif sfc == 9:
                    print('(autonomous) data RSU state')
                    data = message[0:3]
                elif sfc == 10:
                    print('(autonomous) data AID recommendation')
                    data = message[0:6]
                elif sfc == 11:
                    print('(autonomous) data MUS test results')
                    data = message[0:3]
                else:
                    print('Unknown sfc: %d in %s' % (sfc, message.hex(' ')))
                    # note that CC is not received if this happens
                    return
            elif fc == 5:  # command confirm
                print('Command confirm')
                data = message[0:3]
            else:
                print('Unknown fc: %d in %s' % (fc, message.hex(' ')))
                # note that CC is not received if this happens
                return
            # note that data[0] is not used for the message, to synchronize message IDs between sim and socket
            acks = []
            for b in message[LEN + 2:]:
                acks.append(b)
            self.sendMessageBlock(acks, [data[1:]], i=data[0])

        # CC sent data to RSU
        if self.CC in recvPorts:
            acks, messages = self.recvMessageBlock()
            self.acks += acks
            for message in messages:
                fc = message[1] // 32
                sfc = message[1] % 32
                if fc == 0:  # poll
                    print('Poll')
                    data = message + bytes(LEN)
                elif fc == 1:  # parameters message
                    print('Parameters message')
                    data = message + bytes(LEN - 3)
                elif fc == 3:  # command
                    if sfc in [0, 1]:  # OPA, AID legend
                        print('Legend command')
                        data = message[0:LEN + 2]
                    elif sfc in [2, 5, 6, 8, 9]:  # RSU state, brightness, MUS state, MUS test, speed
                        print('Single value command')
                        data = message + bytes(LEN - 1)
                    elif sfc in [3, 4]:  # detector state (2x)
                        print('Detector state command')
                        data = message + bytes(LEN - 4)
                    else:
                        print('Unknown sfc: %d in %s' % (sfc, message.hex(' ')))
                        continue
                elif fc == 4:  # request for data
                    print('Request for data')
                    data = message + bytes(LEN)
                elif fc == 5:  # command confirm
                    print('Command confirm')
                    data = message + bytes(LEN)
                else:
                    print('Unknown fc: %d in %s' % (fc, message.hex(' ')))
                    continue
                assert len(data) == LEN + 2
                self.buffer.append(data)


if __name__ == '__main__':
    RSU = RSUSocket()  # connection to RSU, for in CC
    while 1:
        RSU.mainLoop()
