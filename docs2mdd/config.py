"""설정 파일 로더"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: Optional[str] = None


@dataclass
class DaemonConfig:
    pid_file: str = "/tmp/docs2mdd.pid"
    poll_interval: float = 1.0


@dataclass
class Config:
    src_dir: Path
    dest_dir: Path
    supported_extensions: list[str] = field(default_factory=lambda: [".pdf"])
    assets_dirname: str = "assets"
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)

    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """YAML 설정 파일에서 Config 객체 생성"""
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 경로는 설정 파일 기준 상대 경로로 해석
        config_dir = config_path.parent
        src_dir = config_dir / data.get("src_dir", "./src")
        dest_dir = config_dir / data.get("dest_dir", "./dest")

        logging_data = data.get("logging", {})
        logging_config = LoggingConfig(
            level=logging_data.get("level", "INFO"),
            file=logging_data.get("file"),
        )

        daemon_data = data.get("daemon", {})
        daemon_config = DaemonConfig(
            pid_file=daemon_data.get("pid_file", "/tmp/docs2mdd.pid"),
            poll_interval=daemon_data.get("poll_interval", 1.0),
        )

        return cls(
            src_dir=src_dir.resolve(),
            dest_dir=dest_dir.resolve(),
            supported_extensions=data.get("supported_extensions", [".pdf"]),
            assets_dirname=data.get("assets_dirname", "assets"),
            logging=logging_config,
            daemon=daemon_config,
        )

    @classmethod
    def default(cls) -> "Config":
        """기본 설정으로 Config 객체 생성"""
        return cls(
            src_dir=Path("./src").resolve(),
            dest_dir=Path("./dest").resolve(),
        )

    def setup_logging(self) -> None:
        """로깅 설정 적용"""
        level = getattr(logging, self.logging.level.upper(), logging.INFO)

        handlers: list[logging.Handler] = []

        if self.logging.file:
            handlers.append(logging.FileHandler(self.logging.file))
        else:
            handlers.append(logging.StreamHandler())

        logging.basicConfig(
            level=level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=handlers,
        )

    def ensure_directories(self) -> None:
        """src, dest 디렉토리 생성"""
        self.src_dir.mkdir(parents=True, exist_ok=True)
        self.dest_dir.mkdir(parents=True, exist_ok=True)
