#!/usr/bin/env python3
"""
Setup script for FakeCam.

Provides proper packaging and installation for the FakeCam application.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read long description from README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ""

setup(
    name='fakecam',
    version='2.0.0',
    author='Your Name',
    author_email='your.email@example.com',
    description='Virtual Camera & Microphone for Testing Video Conferencing',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/fakecam',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Video',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: POSIX :: Linux',
    ],
    python_requires='>=3.7',
    install_requires=[
        # No Python package dependencies - all system packages
    ],
    extras_require={
        'dev': [
            'pytest>=6.0',
            'pytest-cov>=2.10',
            'black>=20.8b1',
            'flake8>=3.8',
            'mypy>=0.800',
        ],
    },
    entry_points={
        'console_scripts': [
            'fakecam=fakecam.__main__:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords='virtual camera microphone video audio testing conferencing',
    project_urls={
        'Bug Reports': 'https://github.com/yourusername/fakecam/issues',
        'Source': 'https://github.com/yourusername/fakecam',
        'Documentation': 'https://github.com/yourusername/fakecam/blob/main/README.md',
    },
)
