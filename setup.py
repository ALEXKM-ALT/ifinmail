from setuptools import setup, find_packages

setup(
    name="ifinmail-app",
    version="0.1.0",
    description="A secure, API-first email platform admin tool",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "ifinmail=ifinmail.__main__:main",
        ],
    },
    python_requires=">=3.12",
)
