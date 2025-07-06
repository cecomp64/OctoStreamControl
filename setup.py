
from setuptools import setup

plugin_identifier = "octostreamcontrol"
plugin_package = "octostreamcontrol"
plugin_name = "OctoStreamControl"
plugin_version = "0.1.0"
plugin_description = "WebRTC stream integration and recording control for OctoPrint"
plugin_author = "Carl Svensson"
plugin_author_email = "csvenss2@gmail.com"
plugin_url = "https://github.com/cecomp64/OctoStreamControl"
plugin_license = "AGPL-3.0-or-later"
plugin_requires = []

setup(
    name=plugin_name,
    version=plugin_version,
    description=plugin_description,
    author=plugin_author,
    author_email=plugin_author_email,
    license=plugin_license,
    url=plugin_url,
    packages=[plugin_package],
    include_package_data=True,
    zip_safe=False,
    install_requires=plugin_requires,
    entry_points={
        "octoprint.plugin": [f"{plugin_identifier} = {plugin_package}"]
    },
)
