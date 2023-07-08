from setuptools import setup, find_packages

def parse_requirements(filename):
    """Load requirements from a pip requirements file."""
    with open(filename, 'r') as f:
        lineiter = (line.strip() for line in f)
        return [line for line in lineiter if line and not line.startswith("#")]

install_reqs = parse_requirements("requirements.txt")

setup(
    name='metforce',
    version='0.1.0',
    url='https://github.com/<username>/metforce',
    author='Author Name',
    author_email='author@gmail.com',
    description='Description of my package',
    packages=find_packages(),
    install_requires=install_reqs,
)