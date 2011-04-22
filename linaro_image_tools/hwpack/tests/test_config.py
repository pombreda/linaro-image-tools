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

from StringIO import StringIO

from testtools import TestCase

from linaro_image_tools.hwpack.config import Config, HwpackConfigError


class ConfigTests(TestCase):

    valid_start = (
        "[hwpack]\nname = ahwpack\npackages = foo\narchitectures = armel\n")

    def test_create(self):
        config = Config(StringIO())

    def get_config(self, contents):
        return Config(StringIO(contents))

    def assertConfigError(self, contents, f, *args, **kwargs):
        e = self.assertRaises(HwpackConfigError, f, *args, **kwargs)
        self.assertEqual(contents, str(e))

    def assertValidationError(self, contents, config):
        self.assertConfigError(contents, config.validate)

    def test_validate_no_hwpack_section(self):
        config = self.get_config("")
        self.assertValidationError("No [hwpack] section", config)

    def test_validate_no_name(self):
        config = self.get_config("[hwpack]\n")
        self.assertValidationError("No name in the [hwpack] section", config)

    def test_validate_empty_name(self):
        config = self.get_config("[hwpack]\nname =  \n")
        self.assertValidationError("Empty value for name", config)

    def test_validate_invalid_name(self):
        config = self.get_config("[hwpack]\nname = ~~\n")
        self.assertValidationError("Invalid name: ~~", config)

    def test_validate_invalid_include_debs(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\n"
                "include-debs = if you don't mind\n")
        self.assertValidationError(
            "Invalid value for include-debs: if you don't mind", config)

    def test_validate_invalid_supported(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\nsupport = if you pay us\n")
        self.assertValidationError(
            "Invalid value for support: if you pay us", config)

    def test_validate_no_packages(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\n\n")
        self.assertValidationError(
            "No packages in the [hwpack] section", config)

    def test_validate_empty_packages(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\npackages =  \n")
        self.assertValidationError(
            "No packages in the [hwpack] section", config)

    def test_validate_invalid_package_name(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\npackages = foo  ~~ bar\n")
        self.assertValidationError(
            "Invalid value in packages in the [hwpack] section: ~~",
            config)

    def test_validate_no_architectures(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\npackages = foo\n")
        self.assertValidationError(
            "No architectures in the [hwpack] section", config)

    def test_validate_empty_architectures(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\npackages = foo\n"
                "architectures = \n")
        self.assertValidationError(
            "No architectures in the [hwpack] section", config)

    def test_validate_invalid_package_name_in_assume_installed(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\npackages = foo\n"
                "architectures = armel\nassume-installed = bar ~~\n")
        self.assertValidationError(
            "Invalid value in assume-installed in the [hwpack] section: ~~",
            config)

    def test_validate_no_other_sections(self):
        config = self.get_config(self.valid_start + "\n")
        self.assertValidationError(
            "No sections other than [hwpack]", config)

    def test_validate_other_section_no_sources_entry(self):
        config = self.get_config(self.valid_start + "\n[ubuntu]\n")
        self.assertValidationError(
            "No sources-entry in the [ubuntu] section", config)

    def test_validate_other_section_empty_sources_entry(self):
        config = self.get_config(
                self.valid_start + "\n[ubuntu]\nsources-entry =  \n")
        self.assertValidationError(
            "The sources-entry in the [ubuntu] section is missing the URI",
            config)

    def test_validate_other_section_only_uri_in_sources_entry(self):
        config = self.get_config(
                self.valid_start + "\n[ubuntu]\nsources-entry =  foo\n")
        self.assertValidationError(
            "The sources-entry in the [ubuntu] section is missing the "
            "distribution", config)

    def test_validate_other_section_sources_entry_starting_with_deb(self):
        config = self.get_config(
                self.valid_start
                + "\n[ubuntu]\nsources-entry =  deb http://example.org/ "
                "foo main\n")
        self.assertValidationError(
            "The sources-entry in the [ubuntu] section shouldn't start "
            "with 'deb'", config)

    def test_validate_other_section_sources_entry_starting_with_deb_src(self):
        config = self.get_config(
                self.valid_start
                + "\n[ubuntu]\nsources-entry =  deb-src http://example.org/ "
                "foo main\n")
        self.assertValidationError(
            "The sources-entry in the [ubuntu] section shouldn't start "
            "with 'deb'", config)

    def test_validate_valid_config(self):
        config = self.get_config(
                self.valid_start
                + "\n[ubuntu]\nsources-entry = foo bar\n")
        self.assertEqual(None, config.validate())

    def test_validate_valid_config_with_dash_in_package_name(self):
        config = self.get_config(
                "[hwpack]\nname = ahwpack\n"
                "packages = u-boot\n"
                "architectures = armel\n\n"
                "[ubuntu]\nsources-entry = foo bar\n")
        self.assertEqual(None, config.validate())

    def test_name(self):
        config = self.get_config(
            "[hwpack]\nname = ahwpack\npackages = foo\n"
            "architectures = armel\n")
        self.assertEqual("ahwpack", config.name)

    def test_include_debs(self):
        config = self.get_config(self.valid_start + "include-debs = false\n")
        self.assertEqual(False, config.include_debs)

    def test_include_debs_defaults_true(self):
        config = self.get_config(self.valid_start)
        self.assertEqual(True, config.include_debs)

    def test_include_debs_defaults_true_on_empty(self):
        config = self.get_config(self.valid_start + "include-debs = \n")
        self.assertEqual(True, config.include_debs)

    def test_origin(self):
        config = self.get_config(self.valid_start + "origin = linaro\n")
        self.assertEqual("linaro", config.origin)

    def test_origin_default_None(self):
        config = self.get_config(self.valid_start)
        self.assertEqual(None, config.origin)

    def test_origin_None_on_empty(self):
        config = self.get_config(self.valid_start + "origin =  \n")
        self.assertEqual(None, config.origin)

    def test_maintainer(self):
        maintainer = "Linaro Developers <linaro-dev@lists.linaro.org>"
        config = self.get_config(
            self.valid_start
            + "maintainer = %s\n" % maintainer)
        self.assertEqual(maintainer, config.maintainer)

    def test_maintainer_default_None(self):
        config = self.get_config(self.valid_start)
        self.assertEqual(None, config.maintainer)

    def test_maintainer_None_on_empty(self):
        config = self.get_config(self.valid_start + "maintainer =  \n")
        self.assertEqual(None, config.maintainer)

    def test_support_supported(self):
        config = self.get_config(self.valid_start + "support = supported\n")
        self.assertEqual("supported", config.support)

    def test_support_unsupported(self):
        config = self.get_config(self.valid_start + "support = unsupported\n")
        self.assertEqual("unsupported", config.support)

    def test_support_default_None(self):
        config = self.get_config(self.valid_start)
        self.assertEqual(None, config.support)

    def test_support_None_on_empty(self):
        config = self.get_config(self.valid_start + "support =  \n")
        self.assertEqual(None, config.support)

    def test_packages(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo  bar\n"
            "architectures=armel\n")
        self.assertEqual(["foo", "bar"], config.packages)

    def test_packages_with_newline(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo\n bar\n"
            "architectures=armel\n")
        self.assertEqual(["foo", "bar"], config.packages)

    def test_packages_filters_duplicates(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo bar foo\n"
            "architectures=armel\n")
        self.assertEqual(["foo", "bar"], config.packages)

    def test_sources_single(self):
        config = self.get_config(
            self.valid_start
            + "\n[ubuntu]\nsources-entry = http://example.org foo\n")
        self.assertEqual({"ubuntu": "http://example.org foo"}, config.sources)

    def test_sources_multiple(self):
        config = self.get_config(
            self.valid_start
            + "\n[ubuntu]\nsources-entry = http://example.org foo\n"
            + "\n[linaro]\nsources-entry = http://example.org bar\n")
        self.assertEqual(
            {"ubuntu": "http://example.org foo",
             "linaro": "http://example.org bar"},
            config.sources)

    def test_architectures(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo\narchitectures=foo  bar\n")
        self.assertEqual(["foo", "bar"], config.architectures)

    def test_architectures_with_newline(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo\narchitectures=foo\n bar\n")
        self.assertEqual(["foo", "bar"], config.architectures)

    def test_architectures_filters_duplicates(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo\n"
            "architectures=foo bar foo\n")
        self.assertEqual(["foo", "bar"], config.architectures)

    def test_assume_installed(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo\narchitectures=armel\n"
            "assume-installed=foo  bar\n")
        self.assertEqual(["foo", "bar"], config.assume_installed)

    def test_assume_installed_with_newline(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo\narchitectures=armel\n"
            "assume-installed=foo\n bar\n")
        self.assertEqual(["foo", "bar"], config.assume_installed)

    def test_assume_installed_filters_duplicates(self):
        config = self.get_config(
            "[hwpack]\nname=ahwpack\npackages=foo\narchitectures=armel\n"
            "assume-installed=foo bar foo\n")
        self.assertEqual(["foo", "bar"], config.assume_installed)
