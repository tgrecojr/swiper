"""
Setup configuration for the Swiper package.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    long_description = readme_file.read_text(encoding="utf-8")

setup(
    name="swiper",
    version="0.1.0",
    author="T.J. Greco",
    author_email="tgrecojr@gmail.com",
    description="In-Office Attendance Tracking for Return-to-Office Policies",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tgrecojr/swiper",
    packages=find_packages(exclude=["tests", "tests.*", "docs"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Office/Business",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "click>=8.1.0",
        "pydantic>=2.0.0",
        "pyyaml>=6.0.0",
        "tomli>=2.0.0; python_version < '3.11'",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "swiper=swiper.cli:cli",
        ],
    },
)
