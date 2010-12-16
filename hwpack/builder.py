import logging
import errno

from hwpack.config import Config
from hwpack.hardwarepack import HardwarePack, Metadata
from hwpack.packages import (
    FetchedPackage,
    LocalArchiveMaker,
    PackageFetcher,
    )


logger = logging.getLogger(__name__)


class ConfigFileMissing(Exception):

    def __init__(self, filename):
        self.filename = filename
        super(ConfigFileMissing, self).__init__(
            "No such config file: '%s'" % self.filename)


class HardwarePackBuilder(object):

    def __init__(self, config_path, version, local_debs):
        try:
            with open(config_path) as fp:
                self.config = Config(fp)
        except IOError, e:
            if e.errno == errno.ENOENT:
                raise ConfigFileMissing(config_path)
            raise
        self.config.validate()
        self.version = version
        self.local_debs = local_debs

    def build(self):
        for architecture in self.config.architectures:
            logger.info("Building for %s" % architecture)
            metadata = Metadata.from_config(
                self.config, self.version, architecture)
            hwpack = HardwarePack(metadata)
            sources = self.config.sources
            with LocalArchiveMaker() as local_archive_maker:
                if self.local_debs:
                    sources[None] = (
                        local_archive_maker.sources_entry_for_debs(
                            [FetchedPackage.from_deb(deb)
                             for deb in self.local_debs]))
                hwpack.add_apt_sources(sources)
                logger.info("Fetching packages")
                fetcher = PackageFetcher(
                    sources.values(), architecture=architecture)
                with fetcher:
                    fetcher.ignore_packages(self.config.assume_installed)
                    packages = fetcher.fetch_packages(
                        self.config.packages,
                        download_content=self.config.include_debs)
                    logger.debug("Adding packages to hwpack")
                    hwpack.add_packages(packages)
                    hwpack.add_dependency_package(self.config.packages)
                    with open(hwpack.filename(), 'w') as f:
                        hwpack.to_file(f)
                        logger.info("Wrote %s" % hwpack.filename())
