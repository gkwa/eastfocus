import argparse
import hashlib
import logging
import os
import pathlib
import re
import shutil
import sys
import tempfile
import zipfile as zipmod
from dataclasses import dataclass
from distutils import dir_util

import furl as furlmod
import requests
from omegaconf import OmegaConf

from eastfocus import skeleton


@dataclass
class DropboxPackage:
    version: str
    download_url: str
    filename: str = None

    def __post_init__(self):
        self.update_download_url()
        self.filename = furlmod.furl(self.download_url).path.segments[-1]

    def update_download_url(self):
        furl = furlmod.furl(self.download_url)
        furl.args["dl"] = "1"
        self.download_url = str(furl)

    @property
    def digest(self):
        h = hashlib.new("sha256")
        h.update(self.download_url.encode())
        return h.hexdigest()


def download(dst_dir: pathlib.Path, package: DropboxPackage) -> None:
    pkgfile = dst_dir / package.filename

    if pkgfile.exists():
        return

    r = requests.get(package.download_url, allow_redirects=True)
    if r.status_code == 200:
        path = pathlib.Path(tempfile.gettempdir()) / package.digest
        open(path, "wb").write(r.content)
        shutil.move(path, pkgfile)


def create_package(url) -> DropboxPackage:
    ver = re.search(r"macos\.([\d.]+)", url, re.IGNORECASE).group(1)
    ver = ver.strip(".")
    package = DropboxPackage(version=ver, download_url=url)
    logging.debug(f"{package=}")
    return package


def main(args):
    parser = argparse.ArgumentParser(description="Just a Fibonacci demonstration")
    skeleton.add_common_args(parser)
    parser.add_argument(
        "-r",
        "--release",
        action="store_true",
        default=False,
        help="release this version to latest folder?",
    )
    args = parser.parse_args()
    skeleton.setup_logging(args.loglevel)
    conf = OmegaConf.load("config.yaml")
    package = create_package(conf.release.upstream_url)

    tmp = pathlib.Path("tmp")
    digest_path = tmp / package.digest
    stage_path = digest_path / package.filename
    upload_path = tmp / "upload-to-s3"
    stage10 = digest_path / "stage10"
    vdir = upload_path / "macos" / package.version
    latest = upload_path / "latest"
    latest_macos = latest / "macos"
    ver_txt = vdir / "version.txt"
    guide = pathlib.Path("guides/streambox_iris_quickstart.pdf")

    digest_path.mkdir(exist_ok=True, parents=True)
    upload_path.mkdir(exist_ok=True, parents=True)
    stage10.mkdir(exist_ok=True, parents=True)
    vdir.mkdir(exist_ok=True, parents=True)

    download(digest_path, package)

    shutil.copy(stage_path, stage10)
    orig = pathlib.Path.cwd()
    os.chdir(stage10)

    zipfile = stage10 / "streamox_iris.zip"
    zip_obj = zipmod.ZipFile(zipfile.name, "w")
    zip_obj.write(stage_path.name)
    zip_obj.close()
    os.chdir(orig)

    shutil.copy(zipfile, vdir)

    ver_txt.write_text(package.version)

    latest.mkdir(exist_ok=True, parents=True)
    latest_macos.mkdir(exist_ok=True, parents=True)
    shutil.copy(guide, latest_macos)

    if args.release:
        dir_util.copy_tree(str(vdir), str(latest_macos))


def run():
    """Calls :func:`main` passing the CLI arguments extracted from :obj:`sys.argv`

    This function can be used as entry point to create console scripts with setuptools.
    """
    main(sys.argv[1:])


if __name__ == "__main__":
    run()
