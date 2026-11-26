Changelog
=========

Unreleased
----------

- Initial Sphinx documentation.
- FES2014 tidal currents: ``quantity="u"`` / ``"v"`` (eastward / northward
  velocity, m/s) in ``TideModelFes2014.get_data``, ``TideModel.get_data_on_points``,
  ``export.read_box``, ``get_map``, ``export_map`` and ``predict_at_point``. The
  velocity files are read from the ``eastward_velocity`` and
  ``northward_velocity`` sub folders of the dataset; ``TideModel.has_currents``
  tells whether a dataset has them. The default stays ``"z"`` (water level).
