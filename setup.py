import codecs
from setuptools import setup, find_packages

entry_points = {
    "z3c.autoinclude.plugin": [
        'target = nti.app',
    ],
    'console_scripts': [
        "nti_sync_all_libraries = nti.app.contentlibrary.scripts.nti_sync_all_libraries:main",
        "nti_sync_library_assets = nti.app.contentlibrary.scripts.nti_sync_library_assets:main",
        "nti_remove_package_inaccessible_assets = nti.app.contentlibrary.scripts.nti_remove_package_inaccessible_assets:main"
    ]
}


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
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app'],
    install_requires=[
        'setuptools',
        'docutils',
        'nti.contentlibrary'
    ],
    entry_points=entry_points,
)
