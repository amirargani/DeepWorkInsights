"""Package setup configuration for DeepWorkInsights forecasting package."""

from setuptools import setup, find_packages

setup(
    name="deepwork-insights",
    version="0.1.0",
    description="German Monthly Unemployment Forecasting package with H2O AutoML and Auto-sklearn.",
    author="Amir Argani",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.21,<2.0",
        "scipy>=1.7",
        "scikit-learn>=1.0,<1.5",
        "auto-sklearn==0.15.0",
        "h2o",
        "pandas>=1.5",
        "openpyxl>=3.0",
        "requests>=2.28",
    ],
    python_requires=">=3.8,<=3.11",
)
