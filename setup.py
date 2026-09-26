from setuptools import setup, find_packages

setup(
    name="mtk-unbrick",
    version="0.2.0",
    description="One-click unbrick tool for Xiaomi MTK devices via BROM (mtkclient backend)",
    author="naidrahiqa",
    packages=find_packages(),
    install_requires=[],
    entry_points={
        "console_scripts": [
            "mtk-unbrick=mtk_unbrick.cli:main",
        ],
    },
    python_requires=">=3.8",
)
