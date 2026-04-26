from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="ai_agent_demo",
    version="0.1.0",
    description="Demo agenta AI na lokalnym modelu – wybór narzędzi i anonimizacja danych",
    author="siasty",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
