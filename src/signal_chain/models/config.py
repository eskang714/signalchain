from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class AppConfig:
    conversation_dir: Path
    output_dir: Path

    @classmethod
    def from_yaml(cls, path: Path) -> "AppConfig":
        data = yaml.safe_load(path.read_text())
        return cls(
            conversation_dir=Path(data["conversation_dir"]),
            output_dir=Path(data["output_dir"]),
        )

    def required_dirs(self) -> list[Path]:
        return [self.conversation_dir, self.output_dir]
