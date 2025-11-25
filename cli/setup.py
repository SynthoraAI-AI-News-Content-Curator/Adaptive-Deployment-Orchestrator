"""
Adaptive Deploy CLI Setup
Production-ready CLI tool for deployment management
"""
from setuptools import setup, find_packages

setup(
    name="adaptive-deploy",
    version="1.0.0",
    description="CLI tool for Adaptive Deployment Orchestrator",
    author="Adaptive Deploy Team",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.0",
        "requests>=2.31.0",
        "rich>=13.7.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "tabulate>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "adaptive-deploy=adaptive_deploy.cli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
