from setuptools import setup, find_packages

setup(
    name="load-bearing",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "load_bearing": ["dashboard/dashboard.html", "blacklist.txt"],
    },
    entry_points={
        "console_scripts": [
            "load-bearing=load_bearing.cli:main",
        ],
    },
    python_requires=">=3.8",
    description="Discover and track overused metaphorical language in AI coding assistant logs.",
    author="Volodymyr Orlenko",
    url="https://github.com/orlenko/load-bearing",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
