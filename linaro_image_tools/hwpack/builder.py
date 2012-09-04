# Copyright (C) 2010, 2011 Linaro
#
# Author: James Westby <james.westby@linaro.org>
#
# This file is part of Linaro Image Tools.
#
# Linaro Image Tools is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# Linaro Image Tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Linaro Image Tools; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301,
# USA.

import logging
import errno
import subprocess
import tempfile
import os
import shutil

from linaro_image_tools import cmd_runner

from linaro_image_tools.hwpack.config import Config
from linaro_image_tools.hwpack.hardwarepack import HardwarePack, Metadata
from linaro_image_tools.hwpack.packages import (
    FetchedPackage,
    LocalArchiveMaker,
    PackageFetcher,
    )

from linaro_image_tools.hwpack.hwpack_fields import (
    FILE_FIELD,
    PACKAGE_FIELD,
    SPL_FILE_FIELD,
    SPL_PACKAGE_FIELD,
    COPY_FILES_FIELD,
)

# The fields that hold packages to be installed.
PACKAGE_FIELDS = [PACKAGE_FIELD, SPL_PACKAGE_FIELD]
# Specification of files (boot related) to extract:
# <field_containing_filepaths>: (<take_files_from_package>,
#                                <put_into_this_hwpack_subdir>)
# if <put_into_this_hwpack_subdir> is None, it will be <bootloader_name> for
# global bootloader, or <board>-<bootloader_name> for board-specific
# bootloader
EXTRACT_FILES = {FILE_FIELD: (PACKAGE_FIELD, None),
                 SPL_FILE_FIELD: (SPL_PACKAGE_FIELD, None),
                 COPY_FILES_FIELD: (PACKAGE_FIELD, None)}


logger = logging.getLogger(__name__)


LOCAL_ARCHIVE_LABEL = 'hwpack-local'


class ConfigFileMissing(Exception):

    def __init__(self, filename):
        self.filename = filename
        super(ConfigFileMissing, self).__init__(
            "No such config file: '%s'" % self.filename)


class PackageUnpacker(object):
    def __enter__(self):
        self.tempdir = tempfile.mkdtemp()
        return self

    def __exit__(self, type, value, traceback):
        if self.tempdir is not None and os.path.exists(self.tempdir):
            shutil.rmtree(self.tempdir)

    def get_path(self, package_file_name, file_name=''):
        "Get package or file path in unpacker tmp dir."
        package_dir = os.path.basename(package_file_name)
        return os.path.join(self.tempdir, package_dir, file_name)

    def unpack_package(self, package_file_name):
        # We could extract only a single file, but since dpkg will pipe
        # the entire package through tar anyway we might as well extract all.
        unpack_dir = self.get_path(package_file_name)
        if not os.path.isdir(unpack_dir):
            os.mkdir(unpack_dir)
        p = cmd_runner.run(["tar", "-C", unpack_dir, "-xf", "-"],
                           stdin=subprocess.PIPE)
        cmd_runner.run(["dpkg", "--fsys-tarfile", package_file_name],
                       stdout=p.stdin).communicate()
        p.communicate()

    def get_file(self, package, file):
        # File path passed here must not be absolute, or file from
        # real filesystem will be referenced.
        assert file and file[0] != '/'
        self.unpack_package(package)
        logger.debug("Unpacked package %s." % package)
        temp_file = self.get_path(package, file)
        assert os.path.exists(temp_file), "The file '%s' was " \
            "not found in the package '%s'." % (file, package)
        return temp_file


class HardwarePackBuilder(object):

    def __init__(self, config_path, version, local_debs, out_name=None):
        try:
            with open(config_path) as fp:
                self.config = Config(fp, allow_unset_bootloader=True)
        except IOError, e:
            if e.errno == errno.ENOENT:
                raise ConfigFileMissing(config_path)
            raise
        self.config.validate()
        self.format = self.config.format
        self.version = version
        self.local_debs = local_debs
        self.package_unpacker = None
        self.hwpack = None
        self.packages = None
        self.packages_added_to_hwpack = []
        self.out_name = out_name

    def find_fetched_package(self, packages, wanted_package_name):
        wanted_package = None
        for package in packages:
            if package.name == wanted_package_name:
                wanted_package = package
                break
        else:
            raise AssertionError("Package '%s' was not fetched." % \
                                wanted_package_name)
        return wanted_package

    def add_file_to_hwpack(self, package, wanted_file, target_path):
        if (package.name, wanted_file) in self.packages_added_to_hwpack:
            # Don't bother adding the same package more than once.
            return

        tempfile_name = self.package_unpacker.get_file(
            package.filepath, wanted_file)
        self.packages_added_to_hwpack.append((package.name, target_path))
        return self.hwpack.add_file(target_path, tempfile_name)

    def find_bootloader_packages(self, bootloaders_config):
        """Loop through the bootloaders dictionary searching for packages
        that should be installed, based on known keywords.

        :param bootloaders_config: The bootloaders dictionary to loop through.
        :return A list of packages, without duplicates."""
        boot_packages = []
        for key, value in bootloaders_config.iteritems():
            if isinstance(value, dict):
                boot_packages.extend(self.find_bootloader_packages(value))
            else:
                if key in PACKAGE_FIELDS:
                    boot_packages.append(value)
        # Eliminate duplicates.
        return list(set(boot_packages))

    def extract_bootloader_files(self, board, bootloader_name,
                                 bootloader_conf):
        for key, value in bootloader_conf.iteritems():
            if key in EXTRACT_FILES:
                package_field, dest_path = EXTRACT_FILES[key]
                if not dest_path:
                    dest_path = bootloader_name
                    if board:
                        dest_path += "-" + board
                # Dereference package field to get actual package name
                package = bootloader_conf.get(package_field)
                src_files = value

                # Process scalar and list fields consistently below
                field_value_scalar = False
                if type(src_files) != type([]):
                    src_files = [src_files]
                    field_value_scalar = True

                package_ref = self.find_fetched_package(
                                self.packages, package)
                added_files = []
                for f in src_files:
                    added_files.append(self.add_file_to_hwpack(
                                        package_ref, f, dest_path))
                # Store within-hwpack file paths with the same
                # scalar/list type as original field.
                if field_value_scalar:
                    assert len(added_files) == 1
                    added_files = added_files[0]
                bootloader_conf[key] = added_files

    def extract_files(self, config_dictionary, is_bootloader_config,
                      board=None):
        """Extract (boot) files based on EXTRACT_FILES spec and put
        them into hwpack."""
        self.remove_packages = []
        if is_bootloader_config:
            for bootl_name, bootl_conf in config_dictionary.iteritems():
                self.extract_bootloader_files(board, bootl_name, bootl_conf)
        else:
            # This is board config
            for board, board_conf in config_dictionary.iteritems():
                bootloaders = board_conf['bootloaders']
                self.extract_files(bootloaders, True, board)

        # Clean up no longer needed packages.
        for package in self.remove_packages:
            if package in self.packages:
                self.packages.remove(package)
        self.remove_packages = []

    def build(self):
        for architecture in self.config.architectures:
            logger.info("Building for %s" % architecture)
            metadata = Metadata.from_config(
                self.config, self.version, architecture)
            self.hwpack = HardwarePack(metadata)
            sources = self.config.sources
            with LocalArchiveMaker() as local_archive_maker:
                self.hwpack.add_apt_sources(sources)
                if sources:
                    sources = sources.values()
                else:
                    sources = []
                self.packages = self.config.packages[:]
                # Loop through multiple bootloaders.
                # In V3 of hwpack configuration, all the bootloaders info and
                # packages are in the bootloaders section.
                if self.format.format_as_string == '3.0':
                    if self.config.bootloaders is not None:
                        self.packages.extend(self.find_bootloader_packages(
                                                self.config.bootloaders))
                    if self.config.boards is not None:
                        self.packages.extend(self.find_bootloader_packages(
                                                self.config.boards))
                else:
                    if self.config.bootloader_package is not None:
                        self.packages.append(self.config.bootloader_package)
                    if self.config.spl_package is not None:
                        self.packages.append(self.config.spl_package)
                local_packages = [
                    FetchedPackage.from_deb(deb)
                    for deb in self.local_debs]
                sources.append(
                    local_archive_maker.sources_entry_for_debs(
                        local_packages, LOCAL_ARCHIVE_LABEL))
                self.packages.extend([lp.name for lp in local_packages])
                logger.info("Fetching packages")
                fetcher = PackageFetcher(
                    sources, architecture=architecture,
                    prefer_label=LOCAL_ARCHIVE_LABEL)
                with fetcher:
                    with PackageUnpacker() as self.package_unpacker:
                        fetcher.ignore_packages(self.config.assume_installed)
                        self.packages = fetcher.fetch_packages(
                            self.packages,
                            download_content=self.config.include_debs)

                        # On a v3 hwpack, all the values we need to check are
                        # in the bootloaders and boards section, so we loop
                        # through both of them changing what is necessary.
                        if self.config.format.format_as_string == '3.0':
                            if self.config.bootloaders is not None:
                                self.extract_files(self.config.bootloaders,
                                                   True)
                                metadata.bootloaders = self.config.bootloaders
                            if self.config.boards is not None:
                                self.extract_files(self.config.boards, False)
                                metadata.boards = self.config.boards
                        else:
                            bootloader_package = None
                            if self.config.bootloader_file is not None:
                                assert(self.config.bootloader_package
                                       is not None)
                                bootloader_package = self.find_fetched_package(
                                    self.packages,
                                    self.config.bootloader_package)
                                self.hwpack.metadata.u_boot = \
                                    self.add_file_to_hwpack(
                                        bootloader_package,
                                        self.config.bootloader_file,
                                        self.hwpack.U_BOOT_DIR)

                            spl_package = None
                            if self.config.spl_file is not None:
                                assert self.config.spl_package is not None
                                spl_package = self.find_fetched_package(
                                    self.packages,
                                    self.config.spl_package)
                                self.hwpack.metadata.spl = \
                                    self.add_file_to_hwpack(
                                        spl_package,
                                        self.config.spl_file,
                                        self.hwpack.SPL_DIR)

                            # bootloader_package and spl_package can be
                            # identical
                            if (bootloader_package is not None and
                                bootloader_package in self.packages):
                                self.packages.remove(bootloader_package)
                            if (spl_package is not None and
                                spl_package in self.packages):
                                self.packages.remove(spl_package)

                        logger.debug("Adding packages to hwpack")
                        self.hwpack.add_packages(self.packages)
                        for local_package in local_packages:
                            if local_package not in self.packages:
                                logger.warning(
                                    "Local package '%s' not included",
                                    local_package.name)
                        self.hwpack.add_dependency_package(
                                self.config.packages)
                        out_name = self.out_name
                        if not out_name:
                            out_name = self.hwpack.filename()
                        with open(out_name, 'w') as f:
                            self.hwpack.to_file(f)
                            logger.info("Wrote %s" % out_name)
                        manifest_name = os.path.splitext(out_name)[0]
                        if manifest_name.endswith('.tar'):
                            manifest_name = os.path.splitext(manifest_name)[0]
                        manifest_name += '.manifest.txt'
                        with open(manifest_name, 'w') as f:
                            f.write(self.hwpack.manifest_text())
