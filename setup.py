from setuptools import setup


def readme():
    with open('README.rst') as f:
        return f.read()


setup(name='placement',
      version='0.1',
      description='Collection of VNF placement algorithms',
      long_description=readme(),
      classifiers=[
        'Development Status :: v0.1',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.7',
        'Topic :: Algorithms :: Heuristics',
      ],
      keywords='placement vnf heuristic mapping',
      url='http://github.com/MartinPJorge/placement',
      author='Jorge Martín Pérez',
      author_email='j.martinp@it.uc3m.es',
      license='MIT',
      packages=['placement'],
      install_requires=[
          'networkx==2.2',
      ],
      # test_suite='nose.collector',
      # tests_require=['nose', 'nose-cover3'],
      # entry_points={
      #     'console_scripts': ['funniest-joke=funniest.command_line:main'],
      # },
      include_package_data=True,
      zip_safe=False)
