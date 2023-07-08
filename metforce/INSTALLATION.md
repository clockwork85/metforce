# Installation Instructions for MetForce

Below are the detailed instructions for installing and running MetForce.

## Requirements

- [Anaconda](https://www.anaconda.com/products/distribution) or [Miniconda](https://docs.conda.io/en/latest/miniconda.html)

## Step 1: Clone the Repository

First, clone the repository to your local machine using git:

```bash
git clone https://github.com/clockwork85/metforce.git
```

Then navigate into the repository:

```bash
cd metforce
```

## Step 2: Create and Activate the Conda Environment

Create a new conda environment from the provided environment file:

```bash
conda env create -f environment.yml
```

Activate the new environment:

```bash
conda activate metforce
```

## Step 3: Install Packages with pip

Use pip to install the remaining packages and metforce itself:

```bash
pip install .
```

This command installs the `metforce` package and all of its dependencies.