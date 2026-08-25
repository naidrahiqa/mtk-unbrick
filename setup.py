from setuptools import setup, find_packages

setup(
    name="mtk-unbrick",
    version="0.1.0",
    description="One-click unbrick tool for Xiaomi MTK devices via BROM",
    author="naidrahiqa",
    packages=find_packages(),
    install_requires=[
        "pyusb>=1.2.0",
        "pyserial>=3.5",
        "construct>=2.10",
    ],
    entry_points={
        "console_scripts": [
            "mtk-unbrick=mtk_unbrick.cli:main",
        ],
    },
    python_requires=">=3.8",
)
