Making a release
================

CHT Tide publishes releases to PyPI from a version tag using the
``release`` workflow in
``.github/workflows/publish-to-pypi.yml``. The workflow builds the source
distribution and wheel, publishes them to PyPI with Trusted Publishing, and
creates a GitHub Release.

One-time setup
--------------

Before the first release, configure:

* A GitHub Actions environment named ``release`` in the repository settings.
* A PyPI Trusted Publisher for owner ``Deltares-research``, repository
  ``cht_tide``, workflow ``publish-to-pypi.yml``, and environment ``release``.

Preparing a release
-------------------

1. Update ``cht_tide.__version__`` in ``cht_tide/__init__.py`` and add release
   notes under the matching version in ``docs/changelog.rst``.
2. Open and merge a pull request containing the release changes. Confirm that
   CI passes on the merged commit on ``main``.
3. From an up-to-date local ``main``, create and push an annotated version tag.
   For example, for version ``0.1.2``, run in PowerShell:

   .. code-block:: powershell

      git switch main
      git pull --ff-only origin main
      git tag -a v0.1.2 -m "Release v0.1.2"
      git push origin v0.1.2

   Replace ``v0.1.2`` with the version being released. Tags must use the
   ``vX.Y.Z`` format and match the version in ``cht_tide.__version__``.

Publishing and verification
---------------------------

Pushing the tag starts the ``release`` workflow. It checks that the version is
newer than the latest version on PyPI, builds the distributions, publishes
them, and creates a GitHub Release. Follow the workflow run in the repository's
Actions tab. After it succeeds, verify the release on PyPI and confirm that the
GitHub Release points to the expected tag.

If a workflow job fails, inspect its logs before retrying or changing the tag.
PyPI releases are versioned and should not be overwritten. Conda-forge
publication is a separate step; for a new package, submit a recipe to
``conda-forge/staged-recipes`` after the PyPI source distribution is available.
