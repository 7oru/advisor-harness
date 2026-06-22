from setuptools import find_packages, setup


setup(
    name="multi-agent-advisor",
    version="0.1.0",
    description="Local-first multi-agent advisor harness.",
    packages=find_packages(include=["packages", "packages.*"]),
    package_data={
        "packages.verticals.release_readiness": [
            "prompts/*.md",
            "samples/*.md",
            "schemas/*.json",
        ]
    },
    entry_points={"console_scripts": ["maa=packages.harness.cli:main"]},
    python_requires=">=3.9",
)
