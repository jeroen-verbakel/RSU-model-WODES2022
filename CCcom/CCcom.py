import select
import socket
from typing import List, Tuple

RSUADDR = ('127.0.0.1', 2013)  # Address of the RSU. Use the address of the PLC for HIL
FROMCCADDR = ('127.0.0.1', 3000)  # Internal address
TOCCADDR = ('127.0.0.1', 3001)  # Internal address
HOSTADDR = ('127.0.0.1', 2000)  # Address of this machine. Use an external address for HIL
TIMEOUT = 0.1  # Timeout value for receiving in seconds

LEN = 18  # Length of a message array in the model.

# Lengths of received messages for CC
MESSAGELENGTHS = {
    0x00: 2,  # poll
    0x20: 5,  # parameters
    0x41: 74,  # autonomous MSI states
    0x42: 93,  # autonomous MSI legends
    0x43: 4,  # autonomous MUS state
    0x44: 19,  # autonomous detector states
    0x45: 4,  # autonomous RSU status
    0x49: 3,  # autonomous RSU state
    0x4a: 6,  # autonomous AID recommendation
    0x4b: 3,  # autonomous MUS test result
    0x60: 92,  # command MSI OPA
    0x61: 92,  # command MSI AID
    0x62: 3,  # command RSU state
    0x63: 6,  # command detector state OPA
    0x64: 6,  # command detector state legend
    0x65: 3,  # command brightness
    0x66: 3,  # command MUS state
    0x68: 2,  # command MUS test
    0x69: 3,  # command vMaxDyn
    0x81: 74,  # data MSI states
    0x82: 93,  # data MSI legends
    0x83: 4,  # data MUS state
    0x84: 19,  # data detector states
    0x85: 4,  # data RSU status
    0x86: 98,  # data minute speeds
    0x87: 34,  # data last speed
    0x88: 6,  # data version numbers
    0x89: 3,  # data RSU state
    0x8a: 6,  # data AID recommendation 
    0x8b: 3,  # data MUS test result
    0xA0: 3,  # confirm MSI OPA
    0xA1: 3,  # confirm MSI AID
    0xA2: 3,  # confirm RSU state
    0xA3: 3,  # confirm detector state OPA
    0xA4: 3,  # confirm detector state legend
    0xA5: 3,  # confirm brightness
    0xA6: 3,  # confirm MUS state
    0xA8: 3,  # confirm MUS test
    0xA9: 3  # confirm vMaxDyn
}

# Non-zero default value for MSI commands.
LEGEND_COMMAND = bytes([
    1, 255, 0, 1, 1, 2, 255, 0, 1, 1, 3, 255, 0, 1, 1, 4, 255, 0, 1, 1, 5, 255, 0, 1, 1, 6, 255, 0, 1, 1,
    7, 255, 0, 1, 1, 8, 255, 0, 1, 1, 9, 255, 0, 1, 1, 10, 255, 0, 1, 1, 11, 255, 0, 1, 1, 12, 255, 0, 1, 1,
    13, 255, 0, 1, 1, 14, 255, 0, 1, 1, 15, 255, 0, 1, 1, 16, 255, 0, 1, 1, 17, 255, 0, 1, 1, 18, 255, 0, 1, 1])


def decodeMessageBlock(data: bytes) -> Tuple[List[int], List[bytes]]:
    """ Receive and decode a message block from the RSU. Does not handle timeouts.

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
        if msgType == 64 or msgType == 128:
            # MSI Legend status has variable length
            length = 4
            while data[length]:
                length += 5
            length += 1
        else:
            # all other messages have fixed lengths
            length = MESSAGELENGTHS[msgType]
        msgs.append(data[0:length])
        data = data[length:]
    return acks, msgs


class RSUSocket:
    def __init__(self) -> None:
        # Internal socket to receive messages from CC-sim
        self.fromCC = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.fromCC.bind(FROMCCADDR)

        # Internal socket to send messages to CC-sim (after request)
        self.toCC = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.toCC.bind(TOCCADDR)

        # External socket for all RSU communication
        self.RSU = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.RSU.bind(HOSTADDR)

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
        return bytes([len(block) + 1]) + block

    def send(self, data: bytes):
        """ Send a message to the RSU.
        Low-level send function

        :param data: the message to send
        """
        self.RSU.sendto(data, RSUADDR)
        print("sent %s to %s:%d" % (data.hex(' '), RSUADDR[0], RSUADDR[1]))

    def recv(self) -> bytes:
        """ Receive a message from the RSU.
        Low-level send function, does not handle timeouts.

        :return: the message that was received
        """
        data, addr = self.RSU.recvfrom(256)
        print("received %s from %s:%d" % (data.hex(' '), addr[0], addr[1]))
        return data

    def sendMessageBlock(self, acks: List[int], messages: List[bytes], i=-1):
        """ Encode and send a message block to the RSU. Does not handle timeouts.

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
        # select returns a list of ports that have data present.
        # After TIMEOUT seconds, returns an empty list if no ports have data.
        recvPorts, _, _ = select.select([self.RSU, self.toCC, self.fromCC], [], [], TIMEOUT)

        # CC requests data from RSU
        if self.toCC in recvPorts:
            (_, addr) = self.toCC.recvfrom(255)
            if self.buffer:
                # take the first message from the buffer and prepare an acknowledgement for sending.
                # byte 1 is prefixed to signal a message was received
                data = bytes([1]) + self.buffer.pop(0)
                self.acks.append(data[1])
            else:
                # return a bytelist of all 0's
                data = bytes(LEN + 3)
            self.toCC.sendto(data, addr)
            if len(self.acks) >= 15:
                self.sendMessageBlock(self.acks, [])
                self.acks = []

        # CC sent data to RSU
        if self.fromCC in recvPorts:
            message = self.fromCC.recv(255)
            fc = message[1] // 32
            sfc = message[1] % 32
            if fc == 0:  # poll
                print('Poll')
                data = message[0:2]
            elif fc == 1:  # parameters message
                print('Parameters message')
                data = message[0:5]
            elif fc == 2:  # autonomous message
                print('Unsupported: autonomous message from CC')
                # note that an RSU message is not parsed if this happens
                return
            elif fc == 3:  # command
                if sfc in [0, 1]:  # OPA, AID legend
                    print('Legend command')
                    legends = LEN // 5
                    data = message[0:2 + 5 * legends] + LEGEND_COMMAND[5 * legends:]
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
                    print('Unknown sfc: %d in %s' % (fc, message.hex(' ')))
                    # note that an RSU message is not parsed if this happens
                    return
            elif fc == 4:  # request for data
                print('Request for data')
                data = message[0:2]
            elif fc == 5:  # command confirm
                print('Command confirm')
                data = message[0:2]
            else:
                print('Unknown fc: %d in %s' % (fc, message.hex(' ')))
                # note that an RSU message is not parsed if this happens
                return
            # note that data[0] is not used for the message, to synchronize message IDs between sim and socket
            self.sendMessageBlock(self.acks, [data[1:]], i=data[0])
            # clear the acknowledgement buffer
            self.acks = []

        # RSU sent data to CC
        if self.RSU in recvPorts:
            # ignore acknowledgements
            _, messages = self.recvMessageBlock()
            for message in messages:
                fc = message[1] // 32
                sfc = message[1] % 32
                if fc == 0:  # parameters bericht
                    print('Unsupported: poll from RSU.')
                    continue
                elif fc == 1:  # parameters bericht
                    print('Unsupported: parameters message from RSU.')
                    continue
                elif fc == 3:  # command copy
                    if sfc in [0, 1]:  # OPA, AID legend
                        print('Legend command')
                        data = message[0:LEN + 2]
                    elif sfc in [2, 5, 6, 8, 9]:  # RSU state, brightness, MUS state, MUS test, speed
                        print('Single value command')
                        data = message[0:3] + bytes(LEN - 1)
                    elif sfc in [3, 4]:  # detector state (2x)
                        print('Detector state command')
                        data = message[0:6] + bytes(LEN - 4)
                    else:
                        print('Unknown sfc: %d in %s' % (fc, message.hex(' ')))
                        continue
                elif fc == 2 or fc == 4:  # gegevens bericht
                    if sfc == 0:
                        print('(autonomous) data MSI legend states')
                        self.acks.append(message[0])
                        data = message[0:LEN + 2]
                        if len(data) <= LEN + 2:
                            data += bytes(LEN + 2 - len(data))
                    elif sfc == 1:
                        print('(autonomous) data MSI states')
                        data = message[0:LEN + 2]
                    elif sfc == 2:
                        print('(autonomous) data MSI legends')
                        data = message[0:LEN + 2]
                    elif sfc == 3:
                        print('(autonomous) data MUS state')
                        data = message[0:4] + bytes(LEN - 2)
                    elif sfc == 4:
                        print('(autonomous) data detector states')
                        if LEN <= 17:
                            data = message[0:LEN + 2]
                        else:
                            data = message + bytes(LEN - 17)
                    elif sfc == 5:
                        print('(autonomous) data RSU status')
                        data = message[0:4] + bytes(LEN - 2)
                    elif sfc == 6:
                        # 32 detectors * 2 bytes
                        print('(autonomous) data minute speeds')
                        data = message[0:LEN + 2]
                    elif sfc == 7:
                        # 32 detectors * 1 byte
                        print('(autonomous) data last speed')
                        data = message[0:LEN + 2]
                    elif sfc == 8:
                        print('(autonomous) data version numbers')
                        data = message[0:6] + bytes(LEN - 4)
                    elif sfc == 9:
                        print('(autonomous) data RSU state')
                        data = message[0:3] + bytes(LEN - 1)
                    elif sfc == 10:
                        print('(autonomous) data AID recommendation')
                        data = message[0:4] + bytes(LEN - 2)
                    elif sfc == 11:
                        print('(autonomous) data MUS test results')
                        data = message[0:3] + bytes(LEN - 1)
                    else:
                        print('Unknown (autonomous) data sfc: %d in %s' % (fc, message.hex(' ')))
                        continue
                elif fc == 5:  # command confirm
                    print('Command confirm')
                    data = message[0:3] + bytes(LEN - 1)
                else:
                    print('Unknown fc: %d in %s' % (fc, message.hex(' ')))
                    continue
                assert len(data) == LEN + 2
                self.buffer.append(data)


if __name__ == '__main__':
    RSU = RSUSocket()
    while 1:
        RSU.mainLoop()
