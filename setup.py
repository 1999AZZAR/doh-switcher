from setuptools import setup, find_packages

setup(
    name="doh-switcher",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "flask",
        "requests",
        "httpx",
        "dnslib",
        "flask-socketio",
        "eventlet",
        "flasgger",
        "flask-cors",
        "python-dotenv",
    ],
    entry_points={
        "console_scripts": [
            "doh-switcher=run:main",
        ],
    },
    author="azzar",
    description="A modern, web-based interface to manage and switch between DNS over HTTPS (DoH) providers",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/1999AZZAR/doh-switcher",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.6",
)
