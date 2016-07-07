from __future__ import print_function

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from distutils.ccompiler import new_compiler
from distutils.core import setup
from distutils.errors import CompileError, LinkError
from distutils.extension import Extension
from distutils.sysconfig import customize_compiler

# PEP 440 versioning of the Rados package on PyPI
# Bump this version, after every changeset
# NOTE: This version is not the same as get_ceph_version()

__version__ = '0.0.1'


def get_ceph_version():
    try:
        for line in open(os.path.join(os.path.dirname(__file__), "..", "..", "ceph_ver.h")):
            if "CEPH_GIT_NICE_VER" in line:
                return line.split()[2].strip('"')
        else:
            return "0"
    except IOError:
        return "0"


def get_python_flags():
    cflags = {'I': [], 'extras': []}
    ldflags = {'l': [], 'L': [], 'extras': []}

    if os.environ.get('VIRTUAL_ENV', None):
        python = "python"
    else:
        python = 'python' + str(sys.version_info.major) + '.' + str(sys.version_info.minor)

    python_config = python + '-config'

    for cflag in subprocess.check_output(
            [python_config, "--cflags"]
    ).strip().decode('utf-8').split():
        if cflag.startswith('-I'):
            cflags['I'].append(cflag.replace('-I', ''))
        else:
            cflags['extras'].append(cflag)

    for ldflag in subprocess.check_output(
            [python_config, "--ldflags"]
    ).strip().decode('utf-8').split():
        if ldflag.startswith('-l'):
            ldflags['l'].append(ldflag.replace('-l', ''))
        if ldflag.startswith('-L'):
            ldflags['L'].append(ldflag.replace('-L', ''))
        else:
            ldflags['extras'].append(ldflag)

    return {
        'cflags': cflags,
        'ldflags': ldflags
    }


def check_sanity():
    """
    Test if development headers and library for rados is available by compiling a dummy C program.
    """

    tmp_dir = tempfile.mkdtemp(dir=os.path.dirname(__file__))
    tmp_file = os.path.join(tmp_dir, 'rados_dummy.c')

    with open(tmp_file, 'w') as fp:
        dummy_prog = textwrap.dedent("""
        #include <rados/librados.h>

        int main(void) {
            rados_t cluster;
            rados_create(&cluster, NULL);
            return 0;
        }
        """)
        fp.write(dummy_prog)

    compiler = new_compiler()
    customize_compiler(compiler)

    if set(['MAKEFLAGS', 'MFLAGS', 'MAKELEVEL']).issubset(set(os.environ.keys())):
        # The setup.py has been invoked by a top-level Ceph make.
        # Set the appropriate CFLAGS and LDFLAGS
        CEPH_ROOT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).strip().decode('utf-8')

        compiler.add_include_dir(os.path.join(CEPH_ROOT, 'src', 'include'))
        compiler.add_library_dir(os.path.join(CEPH_ROOT, 'src', '.libs'))

    try:
        compiler.link_executable(
            compiler.compile([tmp_file]),
            os.path.join(tmp_dir, 'rados_dummy'),
            libraries=['rados'],
            output_dir=tmp_dir,
        )

    except CompileError:
        print('\nCompile Error: RADOS development headers not found', file=sys.stderr)
        return False
    except LinkError:
        print('\nLink Error: RADOS library not found', file=sys.stderr)
        return False
    else:
        return True
    finally:
        shutil.rmtree(tmp_dir)


if not check_sanity():
    sys.exit(1)

if '--without-cython' in sys.argv:
    if not os.path.isfile('rados.c'):
        print('Error: Cannot find Cythonized file rados.c', file=sys.stderr)
        print('Retry without using --without-cython', file=sys.stderr)
        sys.exit(1)


    def cythonize(x, **kwargs):
        return x


    sys.argv.remove('--without-cython')
    source = "rados.c"
else:
    from Cython.Build import cythonize

    source = "rados.pyx"

# Disable cythonification if we're not really building anything
if (len(sys.argv) >= 2 and
        any(i in sys.argv[1:] for i in ('--help', 'clean', 'egg_info', '--version')
            )):
    def cythonize(x, **kwargs):
        return x

flags = get_python_flags()

setup(
    name='rados',
    version=__version__,
    description="Python libraries for the Ceph librados library",
    long_description=(
        "This package contains Python libraries for interacting with Ceph's "
        "RADOS library. RADOS is a reliable, autonomic distributed object "
        "storage cluster developed as part of the Ceph distributed storage "
        "system. This is a shared library allowing applications to access "
        "the distributed object store using a simple file-like interface."
    ),
    url='https://github.com/ceph/ceph/tree/master/src/pybind/rados',
    license='LGPLv2+',
    ext_modules=cythonize(
        [
            Extension(
                "rados",
                [source],
                include_dirs=flags['cflags']['I'],
                library_dirs=flags['ldflags']['L'],
                libraries=["rados"] + flags['ldflags']['l'],
                extra_compile_args=flags['cflags']['extras'] + flags['ldflags']['extras'],
            )
        ], build_dir=os.environ.get("CYTHON_BUILD_DIR", None)
    ),
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Cython',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5'
    ],
)
