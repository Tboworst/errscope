from setuptools import setup, find_packages

setup(
    name="beacon-sdk",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests"],
    description="Error tracking SDK for Beacon",
    python_requires=">=3.8",
)
