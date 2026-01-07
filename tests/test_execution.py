"""Tests for sequence loader and execution utilities."""

import pytest
from pathlib import Path
import yaml

from station_service_sdk.execution import SequenceLoader
from station_service_sdk import PackageError, ManifestError


class TestSequenceLoader:
    """Tests for SequenceLoader."""

    @pytest.fixture
    def temp_packages_dir(self, tmp_path):
        """Create temporary packages directory."""
        packages_dir = tmp_path / "sequences"
        packages_dir.mkdir()
        return packages_dir

    @pytest.fixture
    def sample_manifest(self):
        """Create sample manifest data."""
        return {
            "name": "test_sequence",
            "version": "1.0.0",
            "author": "Test Author",
            "description": "Test sequence",
            "entry_point": {
                "module": "sequence",
                "class": "TestSequence",
            },
        }

    def create_package(self, packages_dir: Path, name: str, manifest: dict) -> Path:
        """Helper to create a package directory."""
        pkg_dir = packages_dir / name
        pkg_dir.mkdir()

        manifest_path = pkg_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)

        return pkg_dir

    def test_init(self, temp_packages_dir) -> None:
        """Test SequenceLoader initialization."""
        loader = SequenceLoader(str(temp_packages_dir))

        assert loader.packages_dir == temp_packages_dir

    @pytest.mark.asyncio
    async def test_discover_packages(self, temp_packages_dir, sample_manifest) -> None:
        """Test package discovery."""
        self.create_package(temp_packages_dir, "pkg1", sample_manifest)
        manifest2 = sample_manifest.copy()
        manifest2["name"] = "test_sequence_2"
        self.create_package(temp_packages_dir, "pkg2", manifest2)

        loader = SequenceLoader(str(temp_packages_dir))
        packages = await loader.discover_packages()

        assert len(packages) == 2
        assert "pkg1" in packages
        assert "pkg2" in packages

    @pytest.mark.asyncio
    async def test_discover_skips_hidden_dirs(self, temp_packages_dir, sample_manifest) -> None:
        """Test hidden directories are skipped."""
        self.create_package(temp_packages_dir, "pkg1", sample_manifest)

        hidden_dir = temp_packages_dir / ".hidden"
        hidden_dir.mkdir()

        pycache_dir = temp_packages_dir / "__pycache__"
        pycache_dir.mkdir()

        loader = SequenceLoader(str(temp_packages_dir))
        packages = await loader.discover_packages()

        assert packages == ["pkg1"]

    @pytest.mark.asyncio
    async def test_discover_skips_files(self, temp_packages_dir, sample_manifest) -> None:
        """Test files (not directories) are skipped."""
        self.create_package(temp_packages_dir, "pkg1", sample_manifest)

        # Create a file that should be ignored
        (temp_packages_dir / "readme.txt").write_text("readme")

        loader = SequenceLoader(str(temp_packages_dir))
        packages = await loader.discover_packages()

        assert packages == ["pkg1"]

    @pytest.mark.asyncio
    async def test_load_package(self, temp_packages_dir, sample_manifest) -> None:
        """Test loading a package manifest."""
        self.create_package(temp_packages_dir, "test_pkg", sample_manifest)

        loader = SequenceLoader(str(temp_packages_dir))
        manifest = await loader.load_package("test_pkg")

        assert manifest.name == "test_sequence"
        assert manifest.version == "1.0.0"

    @pytest.mark.asyncio
    async def test_load_package_not_found(self, temp_packages_dir) -> None:
        """Test loading non-existent package raises error."""
        loader = SequenceLoader(str(temp_packages_dir))

        with pytest.raises(PackageError, match="not found"):
            await loader.load_package("nonexistent")

    @pytest.mark.asyncio
    async def test_load_package_no_manifest_file(self, temp_packages_dir) -> None:
        """Test loading package without manifest.yaml raises error."""
        pkg_dir = temp_packages_dir / "no_manifest"
        pkg_dir.mkdir()

        loader = SequenceLoader(str(temp_packages_dir))

        with pytest.raises(PackageError):
            await loader.load_package("no_manifest")

    @pytest.mark.asyncio
    async def test_load_package_invalid_yaml(self, temp_packages_dir) -> None:
        """Test loading package with invalid YAML raises error."""
        pkg_dir = temp_packages_dir / "invalid_yaml"
        pkg_dir.mkdir()

        manifest_path = pkg_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            f.write("invalid: yaml: content: {{{")

        loader = SequenceLoader(str(temp_packages_dir))

        with pytest.raises(ManifestError):
            await loader.load_package("invalid_yaml")

    def test_packages_path_property(self, temp_packages_dir) -> None:
        """Test packages_path property."""
        loader = SequenceLoader(str(temp_packages_dir))

        assert loader.packages_path == temp_packages_dir

    def test_packages_path_with_relative_dir(self, tmp_path, monkeypatch) -> None:
        """Test packages_path with relative directory."""
        # Create sequences dir in tmp_path
        sequences_dir = tmp_path / "sequences"
        sequences_dir.mkdir()

        # Change to tmp_path and use relative path
        monkeypatch.chdir(tmp_path)
        loader = SequenceLoader("sequences")

        assert loader.packages_path == tmp_path / "sequences"


class TestSequenceLoaderCaching:
    """Tests for SequenceLoader caching behavior."""

    @pytest.fixture
    def temp_packages_dir(self, tmp_path):
        """Create temporary packages directory."""
        packages_dir = tmp_path / "sequences"
        packages_dir.mkdir()
        return packages_dir

    @pytest.fixture
    def sample_manifest(self):
        """Create sample manifest data."""
        return {
            "name": "cached_test",
            "version": "1.0.0",
            "entry_point": {
                "module": "sequence",
                "class": "TestSequence",
            },
        }

    def create_package(self, packages_dir: Path, name: str, manifest: dict) -> Path:
        """Helper to create a package directory."""
        pkg_dir = packages_dir / name
        pkg_dir.mkdir()

        manifest_path = pkg_dir / "manifest.yaml"
        with open(manifest_path, "w") as f:
            yaml.dump(manifest, f)

        return pkg_dir

    @pytest.mark.asyncio
    async def test_cache_enabled_by_default(self, temp_packages_dir, sample_manifest) -> None:
        """Test caching is enabled by default."""
        self.create_package(temp_packages_dir, "cached_pkg", sample_manifest)

        loader = SequenceLoader(str(temp_packages_dir))

        manifest1 = await loader.load_package("cached_pkg")
        manifest2 = await loader.load_package("cached_pkg")

        # Same object should be returned (cached)
        assert manifest1 is manifest2

    @pytest.mark.asyncio
    async def test_loaded_packages_cached(self, temp_packages_dir, sample_manifest) -> None:
        """Test loaded packages are cached in _loaded_packages."""
        self.create_package(temp_packages_dir, "pkg", sample_manifest)

        loader = SequenceLoader(str(temp_packages_dir))
        await loader.load_package("pkg")

        assert "pkg" in loader._loaded_packages


class TestSequenceLoaderEmptyDir:
    """Tests for SequenceLoader with empty or missing directories."""

    @pytest.mark.asyncio
    async def test_discover_empty_dir(self, tmp_path) -> None:
        """Test discovering packages in empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        loader = SequenceLoader(str(empty_dir))
        packages = await loader.discover_packages()

        assert packages == []

    @pytest.mark.asyncio
    async def test_discover_missing_dir(self, tmp_path) -> None:
        """Test discovering packages in non-existent directory returns empty list."""
        missing_dir = tmp_path / "missing"

        loader = SequenceLoader(str(missing_dir))
        packages = await loader.discover_packages()

        assert packages == []

    @pytest.mark.asyncio
    async def test_discover_dir_without_manifests(self, tmp_path) -> None:
        """Test directories without manifest.yaml are skipped."""
        packages_dir = tmp_path / "packages"
        packages_dir.mkdir()

        # Create directory without manifest
        no_manifest = packages_dir / "no_manifest"
        no_manifest.mkdir()
        (no_manifest / "readme.txt").write_text("readme")

        loader = SequenceLoader(str(packages_dir))
        packages = await loader.discover_packages()

        assert packages == []
