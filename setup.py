try:
    from setuptools import find_packages, setup
except ImportError:
    # Fallback for cases where setuptools is not available
    import sys
    print("Error: setuptools is required to install roboquant. Please install it with 'pip install setuptools'")
    sys.exit(1)

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", encoding="utf-8") as fh:
    requirements = [
        line.strip() for line in fh if line.strip() and not line.startswith("#")
    ]

setup(
    name="roboquant",
    version="1.0.0",
    author="Daniel Palomo",
    author_email="eldanypalomo@gmail.com",
    description="A quantitative trading system using Donchian Breakout strategy with momentum filter",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/danielpcar9/roboquant",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business :: Financial :: Investment",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.7",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "roboquant-donchian=donchian_strategy:main",
            "roboquant-backtest=backtest_apex_vectorbt:main",
            "roboquant-export=export_mt5_data:main",
            "roboquant-webhook=webhook_receiver:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.bat", "*.md", ".env.example"],
    },
)
