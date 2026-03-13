"""Pure-Python Apple MIDI (RTP-MIDI) server for iOS Network MIDI.

No ALSA, no raveloxmidi, no kernel modules required.

Apple MIDI uses two UDP sockets:
  data port  (5004): session management + RTP-MIDI packets
  control port (5005): session management only

iOS discovers the server via mDNS (_apple-midi._udp) or manual IP entry.
After a two-port handshake the iOS device streams RTP-MIDI to the data port.

The server also browses for peer _apple-midi._udp services and sends outgoing
invites so that apps like AUM (which only route MIDI to devices that connected
TO them) will forward MIDI to us.
"""

import random
import socket
import struct
import threading
import time
import logging

try:
    from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser, ServiceStateChange
    _ZEROCONF_AVAILABLE = True
except ImportError:
    _ZEROCONF_AVAILABLE = False

log = logging.getLogger(__name__)

_MAGIC = b'\xff\xff'


class RtpMidiServer:
    """Apple MIDI / RTP-MIDI UDP server with outgoing connection support.

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
        self._sessions = {}        # ssrc -> peer_name
        self._initiated = set()    # (host, port) we've already sent invites to
        self._lock = threading.Lock()
        self._running = False
        self._data_sock = None
        self._ctrl_sock = None
        self._zeroconf = None

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
        self._setup_mdns()

    def stop(self):
        self._running = False
        if self._zeroconf:
            try:
                self._zeroconf.unregister_all_services()
                self._zeroconf.close()
            except Exception:
                pass
            self._zeroconf = None
        for s in (self._data_sock, self._ctrl_sock):
            if s:
                try:
                    s.close()
                except OSError:
                    pass

    @staticmethod
    def _get_local_ip():
        """Return the outbound LAN IP (avoids 127.0.0.1 in Docker)."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            return s.getsockname()[0]
        except Exception:
            return None
        finally:
            s.close()

    # ── mDNS: advertise + browse ───────────────────────────────────────────

    def _setup_mdns(self):
        if not _ZEROCONF_AVAILABLE:
            log.warning("zeroconf not installed — iOS auto-discovery unavailable")
            return
        local_ip = self._get_local_ip()
        if not local_ip or local_ip.startswith('127.'):
            log.warning("mDNS: could not determine LAN IP, skipping")
            return
        try:
            self._zeroconf = Zeroconf(interfaces=[local_ip])
            # Advertise ourselves
            name = self.OUR_NAME.decode()
            info = ServiceInfo(
                "_apple-midi._udp.local.",
                f"{name}._apple-midi._udp.local.",
                addresses=[socket.inet_aton(local_ip)],
                port=self.data_port,
                properties={},
            )
            self._zeroconf.register_service(info)
            log.info("mDNS: advertised %s at %s:%d", name, local_ip, self.data_port)
            # Browse for peers (e.g. AUM, GarageBand) and connect to them
            ServiceBrowser(self._zeroconf, "_apple-midi._udp.local.",
                           handlers=[self._on_service_state_change])
        except Exception as e:
            log.warning("mDNS setup failed: %s", e)

    def _on_service_state_change(self, zeroconf, service_type, name, state_change):
        if state_change is not ServiceStateChange.Added:
            return
        our_name = self.OUR_NAME.decode()
        if name.startswith(our_name):
            return  # skip ourselves
        try:
            info = zeroconf.get_service_info(service_type, name)
            if not info or not info.addresses:
                return
            host = socket.inet_ntoa(info.addresses[0])
            port = info.port
            log.info("mDNS: discovered peer '%s' at %s:%d — sending invite", name, host, port)
            threading.Thread(target=self._connect_to, args=(host, port),
                             daemon=True, name="rtp-connect").start()
        except Exception as e:
            log.warning("mDNS peer connect error: %s", e)

    def _connect_to(self, host, port):
        """Send Apple MIDI invite to a discovered peer (e.g. AUM)."""
        key = (host, port)
        with self._lock:
            if key in self._initiated:
                return
            self._initiated.add(key)

        token = random.randint(0, 0xFFFFFFFF)
        invite = (_MAGIC + b'IN' +
                  struct.pack('>III', 2, token, self.OUR_SSRC) +
                  self.OUR_NAME + b'\x00')

        # Send invite on data port to peer's advertised port
        self._data_sock.sendto(invite, (host, port))
        log.info("RTP-MIDI: sent invite to %s:%d (data)", host, port)

        # Also send invite on control port to peer's port+1 (Apple convention)
        self._ctrl_sock.sendto(invite, (host, port + 1))
        log.info("RTP-MIDI: sent invite to %s:%d (control)", host, port + 1)

    # ── Receive loop ───────────────────────────────────────────────────────

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
            elif cmd == b'OK':
                self._on_ok(data, addr)
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

    def _on_ok(self, data, addr):
        """Handle OK response to an outgoing invite we sent."""
        if len(data) < 16:
            return
        _version, _token, peer_ssrc = struct.unpack_from('>III', data, 4)
        name = data[16:].rstrip(b'\x00').decode('utf-8', errors='replace')
        log.info("RTP-MIDI: peer '%s' accepted our invite from %s ssrc=%08x", name, addr, peer_ssrc)
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
        # count=0 → 20 bytes, count=1 → 28 bytes, count=2 → 36 bytes
        if len(data) < 20:
            return
        _peer_ssrc, count = struct.unpack_from('>IB', data, 4)
        ts1, = struct.unpack_from('>Q', data, 12)
        now = int(time.monotonic() * 10000)  # 100 µs units
        log.info("RTP-MIDI clock sync: count=%d len=%d", count, len(data))
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
        log.info("RTP-MIDI packet: %d bytes payload, raw=%s", len(payload), payload[:8].hex())
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
