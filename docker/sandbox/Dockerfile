FROM python:3.11-slim

# This trusted supervisor drops the submitted program to UID/GID 65534.
# No app source, uploads, credentials, or host directories enter the image.
COPY runner.py /opt/kavach/runner.py
LABEL io.kavach.sandbox.version="1"
WORKDIR /tmp
ENTRYPOINT ["/usr/local/bin/python3", "-I", "-S", "-u", "/opt/kavach/runner.py"]
