FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV OLA_HOST=10.0.0.10 \
    OLA_PORT=9090 \
    DMX_UNIVERSE=1 \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=5003 \
    FPS=60

EXPOSE 5003

CMD ["python", "server.py"]
