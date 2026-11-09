Changelog
=========

Notable changes to CHT Tide are recorded here. Entries are grouped by type
under each version.

0.1.2 (unreleased)
------------------

Packaging, compatibility, and documentation updates for the next release.

Added
~~~~~

- Support configurable S3-compatible endpoints for tide model and station databases.
- Support constant vertical datum offsets for gridded tide-model constituent data.
- Add Sphinx user and API documentation.
- Declare ``botocore``, ``pyproj``, ``shapely``, and ``xarray`` as direct runtime
  dependencies; the existing runtime dependencies remain in place.

Changed
~~~~~~~

- Update pandas usage for compatibility with pandas 2.2 and later.
- Update the README and installation and API examples for the current package
  interface.

Fixed
~~~~~

- Improve FES2014 constituent loading and interpolation, and fix model and
  station data downloads.

Removed
~~~~~~~

- Remove the unused ``cht_utils`` dependency.

0.1.1 - 2025-01-29
------------------

Added
~~~~~

- Declare ``pandas``, ``geopandas``, ``boto3``, and ``cht_utils`` as runtime
  dependencies.

Changed
~~~~~~~

- Close NetCDF files after reading them.

0.1.0 - 2025-01-13
------------------

Added
~~~~~

- Initial release of CHT Tide.
