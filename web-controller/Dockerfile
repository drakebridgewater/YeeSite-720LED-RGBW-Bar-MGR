FROM python:3.12-slim

WORKDIR /app

# Install ALSA runtime + dev headers (needed to compile python-rtmidi C extension),
# build tools, raveloxmidi (RTP-MIDI daemon for iOS Network MIDI), and avahi for mDNS.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2 \
    libasound2-dev \
    build-essential \
    raveloxmidi \
    avahi-daemon \
    dbus \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY raveloxmidi.conf /etc/raveloxmidi/raveloxmidi.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV OLA_HOST=10.0.0.10 \
    OLA_PORT=9090 \
    DMX_UNIVERSE=1 \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=5003 \
    FPS=60

EXPOSE 5003
EXPOSE 5004/udp
EXPOSE 5005/udp

CMD ["/entrypoint.sh"]
