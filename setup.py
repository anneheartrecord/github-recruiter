from setuptools import setup, find_packages

setup(
    name="github-recruiter",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.0",
        "requests>=2.28",
        "pyyaml>=6.0",
        "rich>=13.0",
    ],
    entry_points={
        "console_scripts": [
            "github-recruiter=github_recruiter.cli:cli",
        ],
    },
    python_requires=">=3.8",
)
