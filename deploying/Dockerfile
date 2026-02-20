# Use the manylinux image for x86_64

# Minimal manylinux image for Python 3.10 wheels
FROM quay.io/pypa/manylinux_2_34_x86_64

# Use Python 3.10 provided by manylinux
ENV PATH=/opt/python/cp310-cp310/bin:$PATH

# Install only minimal system dependencies for wheel installation
RUN yum install -y \
    wget \
    openssl-devel \
    make \
    gcc \
    yum-utils \
    && yum clean all

# Install Docker CLI (for building images via mounted socket)
RUN yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo && \
    yum install -y docker-ce-cli --nobest && \
    yum clean all

# Ensure pip, setuptools, and wheel are up-to-date
RUN python3.10 -m pip install --upgrade pip setuptools wheel

# Cache-busting arg - changing this invalidates cache from here forward (but keeps base layers cached)
ARG CACHE_BUST=0

# Copy makeDeb.py, configs, and Dockerfiles into the image
COPY makeDeb.py /usr/local/bin/makeDeb.py
COPY default_package_config.json /usr/local/bin/default_package_config.json
COPY template.service.in /usr/local/bin/template.service.in
COPY app.Dockerfile /usr/local/bin/app.Dockerfile

# Set working directory for user mounts
WORKDIR /workspace

# Default entrypoint: run makeDeb.py, so you can just pass the config as argument
ENTRYPOINT ["python3", "/usr/local/bin/makeDeb.py"]
