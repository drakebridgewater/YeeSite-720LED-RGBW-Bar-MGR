"""Pure-Python Apple MIDI (RTP-MIDI) server for iOS Network MIDI.

No ALSA, no raveloxmidi, no kernel modules required.

Apple MIDI uses two UDP sockets:
  data port  (5004): session management + RTP-MIDI packets
  control port (5005): session management only

iOS discovers the server via mDNS (_apple-midi._udp) or manual IP entry.
After a two-port handshake the iOS device streams RTP-MIDI to the data port.
"""

import socket
import struct
import threading
import time
import logging

log = logging.getLogger(__name__)

_MAGIC = b'\xff\xff'


class RtpMidiServer:
    """Apple MIDI / RTP-MIDI UDP server.

    Calls midi_callback(msg: list[int]) for each MIDI message received.
    Calls session_callback(connected: bool, name: str) on session changes.
    """

    OUR_SSRC = 0xCAFEBEEF
    OUR_NAME = b'YeeSiteLights'

    def __init__(self, data_port=5004, control_port=5005,
                 midi_callback=None, session_callback=None):
        self.data_port = data_port
        self.control_port = control_port
        self.midi_callback = midi_callback
        self.session_callback = session_callback
        self._sessions = {}   # ssrc -> peer_name
        self._lock = threading.Lock()
        self._running = False
        self._data_sock = None
        self._ctrl_sock = None

    def start(self):
        self._running = True
        self._data_sock = self._bind(self.data_port)
        self._ctrl_sock = self._bind(self.control_port)
        threading.Thread(target=self._recv_loop, args=(self._data_sock, True),
                         daemon=True, name="rtp-data").start()
        threading.Thread(target=self._recv_loop, args=(self._ctrl_sock, False),
                         daemon=True, name="rtp-ctrl").start()
        log.info("RTP-MIDI listening on %d (data) and %d (control)",
                 self.data_port, self.control_port)

    def stop(self):
        self._running = False
        for s in (self._data_sock, self._ctrl_sock):
            if s:
                try:
                    s.close()
                except OSError:
                    pass

    @property
    def connected(self):
        with self._lock:
            return bool(self._sessions)

    @staticmethod
    def _bind(port):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('0.0.0.0', port))
        return s

    def _recv_loop(self, sock, is_data):
        while self._running:
            try:
                data, addr = sock.recvfrom(4096)
                self._dispatch(data, addr, sock, is_data)
            except OSError:
                break
            except Exception as e:
                log.debug("RTP-MIDI recv error: %s", e)

    def _dispatch(self, data, addr, sock, is_data):
        if len(data) < 2:
            return
        if data[:2] == _MAGIC:
            if len(data) < 4:
                return
            cmd = data[2:4]
            if cmd == b'IN':
                self._on_invite(data, addr, sock)
            elif cmd == b'BY':
                self._on_end(data)
            elif cmd == b'CK':
                self._on_clock(data, addr, sock)
        elif is_data and len(data) >= 12:
            self._on_rtp(data)

    # ── Session management ────────────────────────────────────────────────

    def _on_invite(self, data, addr, sock):
        if len(data) < 16:
            return
        version, token, peer_ssrc = struct.unpack_from('>III', data, 4)
        name = data[16:].rstrip(b'\x00').decode('utf-8', errors='replace')
        log.info("RTP-MIDI invite from %s ssrc=%08x name='%s'", addr, peer_ssrc, name)
        reply = (_MAGIC + b'OK' +
                 struct.pack('>III', version, token, self.OUR_SSRC) +
                 self.OUR_NAME + b'\x00')
        sock.sendto(reply, addr)
        with self._lock:
            new = peer_ssrc not in self._sessions
            self._sessions[peer_ssrc] = name
        if new and self.session_callback:
            self.session_callback(True, name)

    def _on_end(self, data):
        if len(data) < 16:
            return
        _, _, peer_ssrc = struct.unpack_from('>III', data, 4)
        with self._lock:
            name = self._sessions.pop(peer_ssrc, None)
            still_connected = bool(self._sessions)
        if name is not None:
            log.info("RTP-MIDI session ended: '%s'", name)
            if self.session_callback:
                self.session_callback(still_connected, name)

    def _on_clock(self, data, addr, sock):
        # CK: FF FF "CK" ssrc(4) count(1) pad(3) ts1(8) [ts2(8) [ts3(8)]]
        if len(data) < 36:
            return
        _peer_ssrc, count = struct.unpack_from('>IB', data, 4)
        ts1, = struct.unpack_from('>Q', data, 12)
        now = int(time.monotonic() * 10000)  # 100 µs units
        if count == 0:
            reply = (_MAGIC + b'CK' +
                     struct.pack('>IB', self.OUR_SSRC, 1) +
                     b'\x00\x00\x00' +
                     struct.pack('>QQ', ts1, now))
            sock.sendto(reply, addr)

    # ── RTP-MIDI ──────────────────────────────────────────────────────────

    def _on_rtp(self, data):
        payload = data[12:]  # skip 12-byte RTP header
        if not payload:
            return
        b_flag = (payload[0] >> 7) & 1
        if b_flag:
            if len(payload) < 2:
                return
            length = ((payload[0] & 0x0F) << 8) | payload[1]
            z_flag = (payload[0] >> 5) & 1
            offset = 2
        else:
            length = payload[0] & 0x0F
            z_flag = (payload[0] >> 5) & 1
            offset = 1
        if length == 0:
            return
        midi_bytes = payload[offset:offset + length]
        if midi_bytes:
            self._parse_commands(bytes(midi_bytes), z_flag)

    def _parse_commands(self, buf, z_flag):
        """Parse MIDI command list from RTP-MIDI payload."""
        pos = 0
        first = True
        running_status = None
        while pos < len(buf):
            # Delta time (variable-length), omitted for first command when Z=1
            if first and z_flag:
                first = False
            else:
                first = False
                delta = 0
                for _ in range(4):
                    if pos >= len(buf):
                        return
                    b = buf[pos]; pos += 1
                    delta = (delta << 7) | (b & 0x7F)
                    if not (b & 0x80):
                        break

            if pos >= len(buf):
                return

            b0 = buf[pos]

            # System Real-Time (single byte, 0xF8–0xFF) — no status consumed
            if b0 >= 0xF8:
                if self.midi_callback:
                    self.midi_callback([b0])
                pos += 1
                continue

            if b0 & 0x80:
                running_status = b0
                pos += 1
            else:
                if running_status is None:
                    pos += 1
                    continue

            status = running_status
            msg_type = status & 0xF0

            if msg_type in (0x80, 0x90, 0xA0, 0xB0, 0xE0):  # 2 data bytes
                if pos + 2 > len(buf):
                    return
                if self.midi_callback:
                    self.midi_callback([status, buf[pos], buf[pos + 1]])
                pos += 2
            elif msg_type in (0xC0, 0xD0):  # 1 data byte
                if pos >= len(buf):
                    return
                if self.midi_callback:
                    self.midi_callback([status, buf[pos]])
                pos += 1
            elif status == 0xF2:  # Song Position Pointer (2 bytes)
                pos += 2
            elif status == 0xF3:  # Song Select (1 byte)
                pos += 1
            else:
                pos += 1
