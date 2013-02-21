from distutils.core import setup

setup(
    name='ClassicUPS',
    version='0.1.0',
    author='Jay Goel',
    author_email='jay@classicspecs.com',
    url='http://github.com/classicspecs/ClassicUPS/',
    packages=['ClassicUPS'],
    description='Library integrating with the UPS API',
    keywords=['UPS'],
    install_requires=[
        'dict2xml == 1.0',
        'xmltodict == 0.4.2',
        'xhtml2pdf == 0.0.4',
        'requests == 0.14.2'
    ],
    classifiers=[
        'Programming Language :: Python',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Intended Audience :: Developers',
        'Development Status :: 4 - Beta'
    ]
)
