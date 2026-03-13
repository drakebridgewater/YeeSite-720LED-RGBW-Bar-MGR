FROM ubuntu:22.04

# Prevent interactive prompts during apt installs
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    libavahi-client3 \
    avahi-daemon \
    dbus \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Use python3/pip3 as python/pip
RUN ln -s /usr/bin/python3 /usr/local/bin/python && \
    ln -s /usr/bin/pip3 /usr/local/bin/pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

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
