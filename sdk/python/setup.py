from setuptools import setup, find_packages

setup(
    name="errscope",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["requests"],
    description="Error tracking SDK for errscope",
    python_requires=">=3.8",
)
