from setuptools import setup, find_packages

setup(
    name="mcx-client-app",
    version="0.1.0",
    description="Motorcortex client app package for robot control",
    author="Coen Smeets",
    author_email="coen@vectioneer.com",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "motorcortex-python",
    ],
    python_requires=">=3.7",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)