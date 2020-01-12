import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sds011",
    version="0.0.2",
    author="Patrick Menschel",
    author_email="menschel.p@posteo.de",
    description="A python 3 interface to a sds011 fine dust sensor",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/menschel/sds011",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable", #used for years without any problems
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering',
        'Topic :: Software Development :: Embedded Systems',
        'Topic :: Utilities',
    ],
    python_requires='>=3.6',
    install_requires=["pyserial"],
    keywords='fine dust sensor nova sds011',

)
