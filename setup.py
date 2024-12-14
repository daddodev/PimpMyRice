import setuptools

with open("README.md", "r", encoding="utf8") as f:
    long_description = f.read()

setuptools.setup(
    name="pimpmyrice",
    version="0.3.2",
    author="daddodev",
    author_email="daddodev@gmail.com",
    description="The overkill rice manager",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/daddodev/pimpmyrice",
    project_urls={
        "Bug Tracker": "https://github.com/daddodev/pimpmyrice/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={"console_scripts": ["pimp=pimpmyrice.__main__:main"]},
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires=">=3.10",
    install_requires=[
        "docopt",
        "jinja2",
        "pyyaml",
        "psutil",
        "requests",
        "scikit-learn",
        "opencv-python",
        "rich",
        "typing_extensions",
        "pydantic",
        "pydantic-extra-types",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-asyncio",
            "mypy",
            "black",
            "types-requests",
            "types-PyYAML",
            "isort",
        ],
    },
)
