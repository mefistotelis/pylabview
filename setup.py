import os
from setuptools import setup, find_packages

def get_long_description():
    this_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists("README.md"):
        return ""
    else:
        with open(os.path.join(this_dir, "README.md")) as readme:
            return readme.read().strip()

setup(name="pylabview",
    description="Python LabVIEW File Type Parser",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    version="0.1.1",
    author="mefistotelis",
    install_requires=["Pillow"],
    url="https://github.com/mefistotelis/pylabview",
    license="MIT",
    packages=find_packages(),
    package_data={'pylabview':['assets/tom-thumb.pbm',
                              'assets/tom-thumb.pil',
                              'assets/tom-thumb.txt']},
    entry_points={'console_scripts':['readRSRC = pylabview.readRSRC:main',
                                     'modRSRC = pylabview.modRSRC:main']},
)
