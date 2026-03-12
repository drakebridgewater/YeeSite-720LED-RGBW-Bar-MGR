FROM ubuntu:22.04

# Prevent interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install runtime deps + build deps for raveloxmidi (not in arm64 repos, must build from source)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    libasound2 \
    libasound2-dev \
    libavahi-client3 \
    libavahi-client-dev \
    libconfig9 \
    libconfig-dev \
    libjson-c5 \
    libjson-c-dev \
    libssl3 \
    libssl-dev \
    avahi-daemon \
    dbus \
    build-essential \
    autoconf \
    automake \
    libtool \
    pkg-config \
    gettext \
    ca-certificates \
    git \
    && git clone --depth 1 https://github.com/ravelox/pimidi.git /tmp/pimidi \
    && cd /tmp/pimidi/raveloxmidi \
    && touch README \
    && autoreconf -fi \
    && ./configure --prefix=/usr \
    && make -j$(nproc) \
    && make install \
    && rm -rf /tmp/pimidi \
    && apt-get remove -y build-essential autoconf automake libtool pkg-config gettext git \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Use python3/pip3 as python/pip
RUN ln -s /usr/bin/python3 /usr/local/bin/python && \
    ln -s /usr/bin/pip3 /usr/local/bin/pip

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
