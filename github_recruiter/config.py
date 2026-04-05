import os
import yaml


DEFAULT_CONFIG = {
    "github": {"token": ""},
    "smtp": {
        "host": "smtp.gmail.com",
        "port": 587,
        "username": "",
        "password": "",
        "from_name": "",
    },
    "search": {
        "min_stars": 100,
        "max_repos": 10,
        "max_contributors": 50,
        "languages": [],
    },
    "sending": {
        "delay_seconds": 10,
        "daily_limit": 50,
        "template": "templates/default.txt",
    },
}


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件，缺失字段用默认值填充"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"配置文件 {config_path} 不存在，请从 config.example.yaml 复制并修改"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        user_config = yaml.safe_load(f) or {}

    config = {}
    for section, defaults in DEFAULT_CONFIG.items():
        if isinstance(defaults, dict):
            config[section] = {**defaults, **(user_config.get(section) or {})}
        else:
            config[section] = user_config.get(section, defaults)

    return config
