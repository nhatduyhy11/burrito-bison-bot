"""Download Argos model packages used by the offline translator."""

import json
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(".tmp/translator-models")
PACKAGES = (
    ("zh_en", "https://argos-net.com/v1/translate-zh_en-1_9.argosmodel"),
    ("en_vi", "https://argos-net.com/v1/translate-en_vi-1_9.argosmodel"),
)


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for pair, url in PACKAGES:
        destination = ROOT / pair
        if (destination / "model/model.bin").is_file():
            print(f"{pair}: already installed", flush=True)
            continue
        archive = ROOT / f"{pair}.zip"
        print(f"Downloading {pair} ...", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=180) as response, archive.open("wb") as f:
            shutil.copyfileobj(response, f)
        with zipfile.ZipFile(archive) as z:
            # Copy files explicitly; never trust archive paths for extraction.
            metadata = next(n for n in z.namelist() if n.endswith("/metadata.json"))
            prefix = metadata.rsplit("/", 1)[0] + "/"
            destination.mkdir(parents=True, exist_ok=True)
            for name in z.namelist():
                if not name.startswith(prefix) or name.endswith("/"):
                    continue
                relative = Path(name[len(prefix):])
                target = (destination / relative).resolve()
                if destination.resolve() not in target.parents:
                    raise ValueError("Unsafe model package path")
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(name) as source, target.open("wb") as f:
                    shutil.copyfileobj(source, f)
        (destination / "source.json").write_text(
            json.dumps({"url": url}, indent=2), encoding="utf-8"
        )
        archive.unlink()
        print(f"{pair}: installed", flush=True)


if __name__ == "__main__":
    main()
