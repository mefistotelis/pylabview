import os
from setuptools import setup, find_packages

def get_long_description():
    this_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists("README.md"):
        return ""
    else:
        with open(os.path.join(this_dir, "README.md")) as readme:
            return readme.read().strip()

setup(
    name="pylabview",
    version="0.1.2",

    description="Python LabVIEW File Type Parser",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",

    author="mefistotelis",

    install_requires=["Pillow"],
    python_requires=">=3.5",

    url="https://github.com/mefistotelis/pylabview",
    license="MIT",

    classifiers=[
      "Intended Audience :: Developers",

      "Programming Language :: Python",
      "Programming Language :: Python :: 3",

      "License :: OSI Approved :: MIT License",

      "Topic :: Utilities",
      "Topic :: Software Development",
    ],

    keywords="labview vi instruments parser extractor reverse-engineering development",

    packages=find_packages(),
    package_data={'pylabview':['assets/tom-thumb.pbm',
                              'assets/tom-thumb.pil',
                              'assets/tom-thumb.txt']},
    entry_points={'console_scripts':['readRSRC = pylabview.readRSRC:main',
                                     'modRSRC = pylabview.modRSRC:main']},

    project_urls={
      "Bug Reports": "https://github.com/mefistotelis/pylabview/issues",
      "Source": "https://github.com/mefistotelis/pylabview/",
    },
)
