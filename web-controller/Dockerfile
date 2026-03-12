FROM python:3.12-slim

WORKDIR /app

# Install ALSA, build tools, avahi for mDNS, and build raveloxmidi from source
# (raveloxmidi is not in Debian Bookworm repos)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2-dev \
    build-essential \
    git \
    autoconf \
    automake \
    libtool \
    pkg-config \
    avahi-daemon \
    dbus \
    libconfig-dev \
    libjson-c-dev \
    && git clone --depth 1 https://github.com/ravelox/pimidi.git /tmp/pimidi \
    && cd /tmp/pimidi/raveloxmidi \
    && autoreconf -fi \
    && ./configure --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && rm -rf /tmp/pimidi \
    && apt-get remove -y git autoconf automake libtool \
    && apt-get autoremove -y \
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
