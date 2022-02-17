import hashlib
import logging
import pathlib
import re
import shutil
import tempfile
from dataclasses import dataclass

import furl as furlmod
import requests
from omegaconf import OmegaConf


@dataclass
class Package:
    version: str
    filename: str
    download_url: str


def download(package: Package) -> None:
    h = hashlib.new("sha256")
    h.update(package.download_url.encode())
    tmpbase = pathlib.Path(".") / h.hexdigest()
    tmpbase.mkdir(exist_ok=True, parents=True)
    pkgfile = tmpbase / package.filename

    if pkgfile.exists():
        return

    r = requests.get(package.download_url, allow_redirects=True)
    if r.status_code == 200:
        path = pathlib.Path(tempfile.gettempdir()) / h.hexdigest()
        open(path, "wb").write(r.content)
        shutil.move(path, pkgfile)


def parse_download_url(conf) -> Package:
    furl = furlmod.furl(conf.release.upstream_url)
    furl.args["dl"] = "1"
    ver = re.search(r"macos\.([\d.]+)", str(furl), re.IGNORECASE).group(1)
    ver = ver.strip(".")
    fname = furl.path.segments[-1]
    url = str(furl)
    pack = Package(filename=fname, version=ver, download_url=url)
    logging.debug(f"{pack=}")
    return pack


def main():
    conf = OmegaConf.load("config.yaml")
    package = parse_download_url(conf)
    download(package)


if __name__ == "__main__":
    main()
