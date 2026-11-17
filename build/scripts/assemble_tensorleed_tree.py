"""Script assemble_tensorleed_tree.

Assembles the TensErLEED tree that the tensorleed test tier runs
against (pytest -m tensorleed, with VIPERLEED_TENSORLEED pointing to
the tree). Used by .github/workflows/tensorleed_tests.yml and by
developers. Needs Internet access, gcc, gfortran, and make (Linux,
macOS) or make.bat (Windows, shipped with the EEASiSSS sources).

Usage: python assemble_tensorleed_tree.py TARGET_DIR

The tree is made from release tags of viperleed/viperleed-tensorleed,
downloaded as archives of the tagged commits (no git needed):
- TensErLEED-v1.61, -v1.74, -v1.75 from tag v1.7.5 (v1.6.1 is the
  same commit), TensErLEED-v2.0.0 and -v2.1.0 from tags v2.0.0 and
  v2.1.0;
- atom_density_files and seSernelius from tag v2.0.0;
- the eeasisss executable, compiled from tag EEASiSSS-v1.0.2.
In TensErLEED-v1.61/lib, the shipped random_.o and MPIrandom_.o are
replaced by a random_.o compiled on this machine, as the installation
instructions for TensErLEED v1.6 require.

TARGET_DIR must not exist or be empty: the script refuses to write
into a non-empty directory. Downloads and builds are made in a
temporary subfolder of TARGET_DIR, which is removed at the end.
"""

__authors__ = (
    'Florian Kraushofer (@fkraushofer)',
    )
__copyright__ = 'Copyright (c) 2019-2026 ViPErLEED developers'
__created__ = '2026-11-17'
__license__ = 'GPLv3+'

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request

ARCHIVE_URL = ('https://github.com/viperleed/viperleed-tensorleed/'
               'archive/{commit}.tar.gz')

# Commits of the release tags. Pinned, so that a moved tag cannot
# change the tree silently.
TAG_COMMITS = {
    'v1.7.5': '71a4cd1f522fe7ab26bf19d09178e57bed544228',
    'v2.0.0': '286211173d560accaef4e046117351a188e3794c',
    'v2.1.0': '22e399826f67837378a95af077eaa3fb048d5cdf',
    'EEASiSSS-v1.0.2': 'c8e3dbfb45e3bb9c3a9aadf37258346aae80bbaa',
    }

# (tag, path in the tag, path in the tree)
TREE_CONTENTS = (
    ('v1.7.5', 'TensErLEED-v1.61', 'TensErLEED-v1.61'),
    ('v1.7.5', 'TensErLEED-v1.74', 'TensErLEED-v1.74'),
    ('v1.7.5', 'TensErLEED-v1.75', 'TensErLEED-v1.75'),
    ('v2.0.0', 'TensErLEED', 'TensErLEED-v2.0.0'),
    ('v2.1.0', 'TensErLEED', 'TensErLEED-v2.1.0'),
    ('v2.0.0', 'atom_density_files', 'atom_density_files'),
    ('v2.0.0', 'seSernelius', 'seSernelius'),
    )

EEASISSS_TAG = 'EEASiSSS-v1.0.2'
EEASISSS_MAKE = (
    ('cmd', '/c', 'make.bat', 'gcc') if sys.platform.startswith('win')
    else ('make', 'gcc')
    )
LEGACY_LIB = Path('TensErLEED-v1.61', 'lib')
WORK_DIR_NAME = '_assemble_tmp'


class TreeAssemblyError(Exception):
    """The TensErLEED tree could not be assembled."""


def assemble_tree(target):
    """Assemble the TensErLEED test tree into a directory.

    Parameters
    ----------
    target : str or Path
        The directory to assemble the tree into. It is created if it
        does not exist.

    Raises
    ------
    TreeAssemblyError
        If target is not an empty directory, or if a compilation
        step fails.
    """
    target = Path(target).resolve()
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise TreeAssemblyError(
            f'{target} exists and is not an empty directory. Remove it '
            'or choose another target.'
            )
    work = target / WORK_DIR_NAME
    work.mkdir(parents=True)
    sources = {tag: _download_tag(tag, work) for tag in TAG_COMMITS}
    for tag, src_path, tree_path in TREE_CONTENTS:
        src = sources[tag] / src_path
        print(f'Copying {tag}:{src_path} to {tree_path}')
        if src.is_dir():
            shutil.copytree(src, target / tree_path)
        else:
            shutil.copy2(src, target / tree_path)
    _compile_random(target / LEGACY_LIB)
    _compile_eeasisss(sources[EEASISSS_TAG], target)
    shutil.rmtree(work)
    print(f'TensErLEED tree assembled in {target}')


def _check_members(tar, tag):
    """Raise TreeAssemblyError if tar may write outside its folder."""
    for member in tar.getmembers():
        path = Path(member.name)
        if (path.is_absolute() or os.pardir in path.parts
                or member.issym() or member.islnk()):
            raise TreeAssemblyError(f'Unsafe member {member.name} in '
                                    f'the archive of {tag}')


def _compile_eeasisss(src, target):
    """Compile eeasisss in folder src and move it to target."""
    print(f'Compiling eeasisss from {EEASISSS_TAG}')
    _run(EEASISSS_MAKE, src)
    for name in ('eeasisss', 'eeasisss.exe'):
        executable = src / name
        if executable.is_file():
            shutil.copy2(executable, target / name)
            return
    raise TreeAssemblyError(f'Compiling eeasisss produced no executable '
                            f'in {src}')


def _compile_random(lib):
    """Replace the shipped randomizer objects with a compiled one."""
    print(f'Compiling random_.o in {lib}')
    for name in ('random_.o', 'MPIrandom_.o'):
        (lib / name).unlink()
    _run(['gcc', '-O3', '-c', 'random_.c', '-o', 'random_.o'], lib)


def _download_tag(tag, work):
    """Download and unpack the archive of tag; return its root."""
    url = ARCHIVE_URL.format(commit=TAG_COMMITS[tag])
    print(f'Downloading {tag} from {url}')
    archive = work / f'{tag}.tar.gz'
    with urllib.request.urlopen(url) as response, archive.open('wb') as file:
        shutil.copyfileobj(response, file)
    unpacked = work / tag
    with tarfile.open(archive) as tar:
        if hasattr(tarfile, 'data_filter'):  # Python 3.12, backports
            tar.extractall(unpacked, filter='data')
        else:
            _check_members(tar, tag)
            tar.extractall(unpacked)
    archive.unlink()
    root, = unpacked.iterdir()  # GitHub archives have one root folder
    return root


def _run(command, cwd):
    """Run command in folder cwd, raise TreeAssemblyError on failure."""
    try:
        subprocess.run(command, cwd=str(cwd), check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise TreeAssemblyError(
            f'{subprocess.list2cmdline(command)} failed in {cwd}: {exc}'
            ) from exc


def main():
    """Assemble the TensErLEED test tree into the directory given."""
    parser = argparse.ArgumentParser(
        description='Assemble the TensErLEED tree for the tensorleed '
                    'test tier into TARGET_DIR (must not exist or be '
                    'empty).',
        )
    parser.add_argument('target_dir', help='directory to assemble into')
    args = parser.parse_args()
    try:
        assemble_tree(args.target_dir)
    except TreeAssemblyError as exc:
        sys.exit(f'Error: {exc}')


if __name__ == '__main__':
    main()
