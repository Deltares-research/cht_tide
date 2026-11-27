"""Tests for TideModelDatabase: S3 store settings and online metadata refresh."""

import os

import toml

from cht_tide.database import TideModelDatabase

OLD_METADATA = {
    "longname": "FES 2014 (extrap)",
    "format": "fes2014",
    "s3_bucket": "deltares-ddb",
    "s3_key": "data/tide_models/fes2014_extrap",
    "files": ["m2.nc"],
}


class FakeS3Client:
    """Stand-in for a boto3 S3 client; ``objects`` maps (bucket, key) to text."""

    def __init__(self, objects):
        self.objects = objects
        self.requests = []

    def download_file(self, Bucket, Key, Filename):  # noqa: N803 (boto3 names)
        self.requests.append((Bucket, Key))
        if (Bucket, Key) not in self.objects:
            raise RuntimeError(f"404 {Bucket}/{Key}")
        with open(Filename, "w") as f:
            f.write(self.objects[(Bucket, Key)])


def _make_local_database(path, datasets):
    """Write tide_models.tml and a metadata.tml per dataset."""
    entries = []
    for name, metadata in datasets.items():
        os.makedirs(os.path.join(path, name), exist_ok=True)
        with open(os.path.join(path, name, "metadata.tml"), "w") as f:
            toml.dump(metadata, f)
        entries.append({"name": name})
    with open(os.path.join(path, "tide_models.tml"), "w") as f:
        toml.dump({"dataset": entries}, f)


def test_database_store_wins_over_metadata(tmp_path):
    local = dict(OLD_METADATA, longname="Local only")
    del local["s3_bucket"], local["s3_key"]
    _make_local_database(
        str(tmp_path), {"fes2014_extrap": OLD_METADATA, "my_local_model": local}
    )
    db = TideModelDatabase(
        path=str(tmp_path),
        s3_bucket="delftdashboard",
        s3_key="data/tide_models",
        s3_endpoint="https://s3.example.org",
    )
    fes = db.get_dataset("fes2014_extrap")
    assert fes.s3_bucket == "delftdashboard"
    assert fes.s3_key == "data/tide_models/fes2014_extrap"
    assert fes.s3_endpoint == "https://s3.example.org"
    # A dataset without s3_bucket in its metadata is not downloaded from S3
    assert getattr(db.get_dataset("my_local_model"), "s3_bucket", None) is None


def test_metadata_used_without_database_store(tmp_path):
    _make_local_database(str(tmp_path), {"fes2014_extrap": OLD_METADATA})
    db = TideModelDatabase(path=str(tmp_path))
    fes = db.get_dataset("fes2014_extrap")
    assert fes.s3_bucket == "deltares-ddb"
    assert fes.s3_key == "data/tide_models/fes2014_extrap"


def test_online_check_refreshes_and_adds_metadata(tmp_path):
    _make_local_database(str(tmp_path), {"fes2014_extrap": OLD_METADATA})
    # A local entry with its own path must survive the rewrite of tide_models.tml
    # (written as text with a literal string: toml.dump does not escape the
    # backslashes of a Windows path)
    tml_file = tmp_path / "tide_models.tml"
    with open(tml_file, "a") as f:
        f.write(f"\n[[dataset]]\nname = \"elsewhere\"\npath = '{tmp_path / 'x'}'\n")

    new_metadata = dict(OLD_METADATA, s3_bucket="delftdashboard", currents=True)
    other = dict(OLD_METADATA, longname="Other model")
    client = FakeS3Client(
        {
            ("delftdashboard", "data/tide_models/tide_models.tml"): toml.dumps(
                {"dataset": [{"name": "fes2014_extrap"}, {"name": "other"}]}
            ),
            (
                "delftdashboard",
                "data/tide_models/fes2014_extrap/metadata.tml",
            ): toml.dumps(new_metadata),
            ("delftdashboard", "data/tide_models/other/metadata.tml"): toml.dumps(
                other
            ),
        }
    )
    db = TideModelDatabase(
        path=str(tmp_path), s3_bucket="delftdashboard", s3_key="data/tide_models"
    )
    assert not db.get_dataset("fes2014_extrap").has_currents
    db.s3_client = client
    db.check_online_database()

    # Existing dataset: metadata refreshed (currents now on)
    fes = db.get_dataset("fes2014_extrap")
    assert fes.has_currents
    assert toml.load(tmp_path / "fes2014_extrap" / "metadata.tml")["currents"]
    # New dataset added; existing entries (with path) kept, no duplicates
    assert db.get_dataset("other") is not None
    names = [d["name"] for d in toml.load(tml_file)["dataset"]]
    assert names == ["fes2014_extrap", "elsewhere", "other"]
    assert toml.load(tml_file)["dataset"][1]["path"] == str(tmp_path / "x")


def test_online_check_keeps_local_metadata_if_download_fails(tmp_path):
    _make_local_database(str(tmp_path), {"fes2014_extrap": OLD_METADATA})
    client = FakeS3Client(
        {
            ("delftdashboard", "data/tide_models/tide_models.tml"): toml.dumps(
                {"dataset": [{"name": "fes2014_extrap"}]}
            ),
        }
    )
    db = TideModelDatabase(
        path=str(tmp_path), s3_bucket="delftdashboard", s3_key="data/tide_models"
    )
    db.s3_client = client
    db.check_online_database()

    folder = tmp_path / "fes2014_extrap"
    assert toml.load(folder / "metadata.tml")["s3_bucket"] == "deltares-ddb"
    assert sorted(os.listdir(folder)) == ["metadata.tml"]
    assert db.get_dataset("fes2014_extrap") is not None
