from setuptools import setup, find_packages

setup(
    name="symphony_tools",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "bech32",
        #TODO add other dependencies
    ],
    entry_points={
        "console_scripts": [
            "symphony-bech32=symphony_tools.cli:bech32_main",
            "symphony-snapshot=symphony_tools.cli:snapshot_main",
        ],
    },
    extras_require={
        "dev": [
            "pytest",
        ],
    },
)