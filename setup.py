import codecs
from setuptools import setup, find_packages

entry_points = {
    "z3c.autoinclude.plugin": [
        'target = nti.app',
    ],
    'console_scripts': [
        "nti_sync_all_libraries = nti.app.contentlibrary.scripts.nti_sync_all_libraries:main",
        "nti_sync_library_assets = nti.app.contentlibrary.scripts.nti_sync_library_assets:main",
    ]
}


TESTS_REQUIRE = [
    'nti.app.testing',
    'nti.testing',
    'zope.testrunner',
]

def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.contentlibrary',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="NTI app contentlibrary",
    long_description=_read('README.rst'),
    license='Apache',
    keywords='pyramid contentlibrary',
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
    ],
    url="https://github.com/NextThought/nti.app.contentlibrary",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app'],
    install_requires=[
        'setuptools',
        'nti.contentfragments',
        'nti.contentlibrary'
    ],
    extras_require={
        'test': TESTS_REQUIRE,
    },
    entry_points=entry_points,
)
