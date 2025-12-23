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
 && yum clean all

# Ensure pip, setuptools, wheel, Cython, and auditwheel are up-to-date
RUN python3.10 -m pip install --upgrade pip setuptools wheel cython auditwheel

# Default command: build wheels from mounted requirements.txt and repair them into wheels_out
CMD ["bash", "-c", "\
    mkdir -p wheels && \
    pip wheel -r requirements.txt -w wheels_tmp && \
    for whl in wheels_tmp/*.whl; do \
        auditwheel repair \"$whl\" -w wheels 2>/dev/null || cp \"$whl\" wheels/; \
    done && \
    rm -rf wheels_tmp && \
    if [ -n \"$USER_ID\" ] && [ -n \"$GROUP_ID\" ]; then \
        chown -R $USER_ID:$GROUP_ID wheels 2>/dev/null || true; \
    fi && \
    chmod -R a+rwX wheels \
"]
