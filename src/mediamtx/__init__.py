import urllib.request
import platform
import tarfile
import yaml
import subprocess
import os
import zipfile
import logging
import stat

logger = logging.getLogger(__name__)

# Allow overriding the version at runtime, fallback to the current default
MEDIAMTX_VERSION = os.environ.get("MEDIAMTX_VERSION", "v1.14.0")

def _detect_arch():
    m = platform.machine().lower()
    if m in ("x86_64", "amd64"):
        return "amd64"
    if m in ("aarch64", "arm64"):
        return "arm64"
    if m in ("armv7l", "armv7"):
        return "armv7"
    return m  # unknown -> will error later with a clear message

def _build_download_url(system: str, arch: str) -> str:
    base = f"https://github.com/bluenviron/mediamtx/releases/download/{MEDIAMTX_VERSION}"
    if system == "Linux":
        if arch == "amd64":
            return f"{base}/mediamtx_{MEDIAMTX_VERSION}_linux_amd64.tar.gz"
        if arch == "arm64":
            return f"{base}/mediamtx_{MEDIAMTX_VERSION}_linux_arm64.tar.gz"
        if arch == "armv7":
            return f"{base}/mediamtx_{MEDIAMTX_VERSION}_linux_armv7.tar.gz"
        raise Exception(f"Unsupported Linux arch: {arch}")
    if system == "Windows":
        # Keeping only amd64 here; extend if you need 32-bit
        return f"{base}/mediamtx_{MEDIAMTX_VERSION}_windows_amd64.zip"
    raise Exception(f"Unsupported OS: {system}")

class Singleton(object):
    def __new__(cls, *args, **kargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super(Singleton, cls).__new__(cls)
        return cls._instance

class MediaMTX(Singleton):
    def __init__(self):
        self.system = platform.system()
        arch = _detect_arch()
        url = _build_download_url(self.system, arch)

        os.makedirs("mediamtx", exist_ok=True)

        binary = os.path.join(
            "mediamtx", "mediamtx.exe" if self.system == "Windows" else "mediamtx"
        )
        yaml_path = os.path.join("mediamtx", "mediamtx.yml")

        # Download only if missing
        if not (os.path.exists(binary) and os.path.exists(yaml_path)):
            logger.info(f"Downloading MediaMTX ({self.system}, {arch}) from {url} ...")
            if url.endswith(".tar.gz"):
                tmp = os.path.join("mediamtx", "mediamtx.tar.gz")
                urllib.request.urlretrieve(url, tmp)
                with tarfile.open(tmp, mode="r:gz") as tar:
                    tar.extractall("mediamtx")
                os.remove(tmp)
            elif url.endswith(".zip"):
                tmp = os.path.join("mediamtx", "mediamtx.zip")
                urllib.request.urlretrieve(url, tmp)
                with zipfile.ZipFile(tmp, "r") as zip_ref:
                    zip_ref.extractall("mediamtx")
                os.remove(tmp)
            else:
                raise Exception(f"Unknown archive format for URL: {url}")

        # Ensure executable bit on Linux
        if self.system == "Linux" and os.path.exists(binary):
            st = os.stat(binary)
            os.chmod(binary, st.st_mode | stat.S_IEXEC)

        # Final check
        if not os.path.exists(binary):
            raise FileNotFoundError(f"MediaMTX binary not found at {binary}")
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"MediaMTX config not found at {yaml_path}")

        # Load YAML so add_path() can work without re-reading
        with open(yaml_path, encoding="utf-8") as f:
            self.yaml = yaml.safe_load(f)

    def start(self):
        logger.info("Starting MediaMTX...")
        binary = os.path.join(
            "mediamtx", "mediamtx.exe" if self.system == "Windows" else "mediamtx"
        )
        yaml_path = os.path.join("mediamtx", "mediamtx.yml")
        self.proc = subprocess.Popen([binary, yaml_path])
        logger.info("Process Started")

    def stop(self):
        logger.info("Stopping MediaMTX...")
        if hasattr(self, "proc") and self.proc:
            self.proc.kill()
        logger.info("Stopped MediaMTX")

    def get_yaml(self):
        with open("mediamtx/mediamtx.yml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def set_yaml(self, data):
        with open("mediamtx/mediamtx.yml", "w", encoding="utf-8") as f:
            return yaml.safe_dump(data, f)

    def add_path(self, name, url):
        self.yaml["paths"][name] = {"source": url}
        with open("mediamtx/mediamtx.yml", "w", encoding="utf-8") as f:
            yaml.safe_dump(self.yaml, f)