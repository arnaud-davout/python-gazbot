import os

from setuptools import setup, find_packages

PACKAGE_NAME = "python_gazbot"
VERSION = "1.0"

ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
with open("{}/requirements.txt".format(ROOT_PATH)) as _f:
    install_requires = [line.strip() for line in _f if line.strip()]

setup(
    name=PACKAGE_NAME,
    version=VERSION,
    author="Arnaud d'Avout",
    author_email="arnaud@davout.net",
    description="Python Gazbot",
    license="MIT",
    packages=find_packages(),
    package_data={},
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    extras_require={}
)   
