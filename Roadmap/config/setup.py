# setup.py - Đóng gói module Roadmap (optional)
from setuptools import setup, find_packages

setup(
    name="roadmap-module",
    version="2.0.0",
    description="Career Roadmap Generator - 4-layer knowledge graph based",
    author="Claude Code",
    author_email="noreply@anthropic.com",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[],  # no external dependencies
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
