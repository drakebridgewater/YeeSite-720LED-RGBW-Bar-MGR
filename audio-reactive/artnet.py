"""
Minimal ArtNet OpDmx UDP sender.
No dependencies beyond the Python standard library.
"""
import socket
import struct


class ArtNetSender:
    _HEADER   = b"Art-Net\x00"
    _OP_DMX   = 0x5000
    _PROT_VER = 14

    def __init__(self, host: str, port: int = 6454, universe: int = 0):
        self.host     = host
        self.port     = port
        self.universe = universe
        self._seq     = 0
        self._sock    = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, dmx_data: list[int]) -> None:
        """
        Send a DMX frame as an ArtNet OpDmx packet.

        dmx_data: list of ints (0–255), up to 512 channels.
                  Length is rounded up to the nearest even number as required by the spec.
        """
        n = min(512, len(dmx_data))
        if n % 2:
            n += 1  # ArtNet requires even length

        payload = bytearray(n)
        for i in range(min(n, len(dmx_data))):
            payload[i] = max(0, min(255, dmx_data[i]))

        self._seq = (self._seq + 1) % 256

        packet = (
            self._HEADER
            + struct.pack("<H", self._OP_DMX)      # OpCode, little-endian
            + struct.pack(">H", self._PROT_VER)    # Protocol version, big-endian
            + bytes([self._seq, 0])                # Sequence, Physical
            + struct.pack("<H", self.universe)     # Universe, little-endian
            + struct.pack(">H", n)                 # DMX length, big-endian
            + bytes(payload)
        )
        self._sock.sendto(packet, (self.host, self.port))

    def close(self) -> None:
        self._sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
