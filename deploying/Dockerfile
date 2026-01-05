# Use the manylinux image for x86_64
FROM quay.io/pypa/manylinux_2_34_x86_64

WORKDIR /app

# Use Python 3.10 provided by manylinux
ENV PATH=/opt/python/cp310-cp310/bin:$PATH

# Optional: install Rust for packages that require it
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH=/root/.cargo/bin:$PATH

# Install system dependencies (BLAS/LAPACK, compilers, etc.)
RUN yum install -y \
    make cmake wget tar dpkg-dev \
    openblas-devel \
    blas-devel lapack-devel gfortran \
    openssl-devel pkgconfig \
    libquadmath libquadmath-devel \
    jq \
 && yum clean all

# Ensure pip, setuptools, wheel, Cython, and auditwheel are up-to-date
RUN python3.10 -m pip install --upgrade pip setuptools wheel cython auditwheel

# Copy makeDeb.py and default_service_config.json into the image
COPY makeDeb.py /usr/local/bin/makeDeb.py
COPY default_service_config.json /usr/local/bin/default_service_config.json
COPY template.service.in /usr/local/bin/template.service.in

# Set working directory for user mounts
WORKDIR /workspace

# Default entrypoint: run makeDeb.py, so you can just pass the config as argument
ENTRYPOINT ["python3", "/usr/local/bin/makeDeb.py"]
