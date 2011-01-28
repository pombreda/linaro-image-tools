import platform

try:
    from CommandNotFound import CommandNotFound
except ImportError:
    CommandNotFound = None

from linaro_media_create import cmd_runner


def install_package_providing(command):
    """Install a package which provides the given command.

    If we can't find any package which provides it, raise
    UnableToFindPackageProvidingCommand.
    """
    if CommandNotFound is None:
        raise UnableToFindPackageProvidingCommand(
            "Cannot lookup a package which provides %s" % command)

    packages = CommandNotFound().getPackages(command)
    if len(packages) == 0:
        raise UnableToFindPackageProvidingCommand(
            "Unable to find any package providing %s" % command)

    # TODO: Ask the user to pick a package when there's more than one that
    # provide the given command.
    package, _ = packages[0]
    print ("Installing required command %s from package %s"
           % (command, package))
    cmd_runner.run(['apt-get', 'install', package], as_root=True).wait()


def ensure_command(command):
    """Ensure the given command is available.

    If it's not, look up a package that provides it and install that.
    """
    try:
        cmd_runner.run(
            ['which', command], stdout=open('/dev/null', 'w')).wait()
    except cmd_runner.SubcommandNonZeroReturnValue:
        install_package_providing(command)


def is_arm_host():
    return platform.machine().startswith('arm')


class UnableToFindPackageProvidingCommand(Exception):
    """We can't find a package which provides the given command."""