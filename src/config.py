import os
import yaml
import tempfile
from pathlib import Path
from typing import Any

CONFIG_SCHEMA = {
    "EMBY_SERVER_URL": {
        "type": "string",
        "default": None,
        "env_var": "EMBY_SERVER_URL",
        "description": "Emby/Jellyfin 服务器地址",
    },
    "SUB_CACHE_SIZE": {
        "type": "integer",
        "default": 50,
        "env_var": "SUB_CACHE_SIZE",
        "description": "字幕缓存大小（条目数）",
        "min": 1,
        "max": 10000,
    },
    "SUB_CACHE_TTL": {
        "type": "integer",
        "default": 60,
        "env_var": "SUB_CACHE_TTL",
        "description": "字幕缓存过期时间（分钟）",
        "min": 1,
        "max": 1440,
    },
    "FONT_CACHE_SIZE": {
        "type": "integer",
        "default": 30,
        "env_var": "FONT_CACHE_SIZE",
        "description": "字体缓存大小（条目数）",
        "min": 1,
        "max": 10000,
    },
    "FONT_CACHE_TTL": {
        "type": "integer",
        "default": 30,
        "env_var": "FONT_CACHE_TTL",
        "description": "字体缓存过期时间（分钟）",
        "min": 1,
        "max": 1440,
    },
    "LOG_LEVEL": {
        "type": "enum",
        "default": "INFO",
        "env_var": "LOG_LEVEL",
        "description": "日志级别",
        "enum_values": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    },
    "ERROR_DISPLAY": {
        "type": "float",
        "default": 0.0,
        "env_var": "ERROR_DISPLAY",
        "description": "在字幕中显示错误信息的时长（0-60秒，0为关闭）",
        "min": 0,
        "max": 60,
    },
    "MISS_LOGS": {
        "type": "boolean",
        "default": False,
        "env_var": "MISS_LOGS",
        "description": "启用缺失字体日志记录",
    },
    "MISS_GLYPH_LOGS": {
        "type": "boolean",
        "default": False,
        "env_var": "MISS_GLYPH_LOGS",
        "description": "启用缺失字形日志记录",
    },
    "DISABLE_ONLINE_FONTS": {
        "type": "boolean",
        "default": False,
        "env_var": "DISABLE_ONLINE_FONTS",
        "description": "禁用在线字体下载",
    },
    "RENAMED_FONT_RESTORE": {
        "type": "boolean",
        "default": True,
        "env_var": "RENAMED_FONT_RESTORE",
        "description": "恢复字幕中被重命名的字体名称",
    },
    "EMBY_WEB_EMBED_FONT": {
        "type": "boolean",
        "default": True,
        "env_var": "EMBY_WEB_EMBED_FONT",
        "description": "修改 Emby JS 以支持网页字体渲染",
    },
    "POOL_CPU_MAX": {
        "type": "integer",
        "default": 0,
        "env_var": "POOL_CPU_MAX",
        "description": "最大 CPU 池大小（0 = 自动）",
        "min": 0,
        "max": 128,
    },
    "SRT_2_ASS_FORMAT": {
        "type": "string",
        "default": None,
        "env_var": "SRT_2_ASS_FORMAT",
        "description": "SRT 转 ASS 的格式模板",
    },
    "SRT_2_ASS_STYLE": {
        "type": "string",
        "default": None,
        "env_var": "SRT_2_ASS_STYLE",
        "description": "SRT 转 ASS 的字幕样式",
    },
    "HDR_SATURATION": {
        "type": "float",
        "default": 1.0,
        "env_var": "HDR_SATURATION",
        "description": "HDR 字幕饱和度（0.0-1.0）",
        "min": 0.0,
        "max": 1.0,
    },
    "HDR_BRIGHTNESS": {
        "type": "float",
        "default": 1.0,
        "env_var": "HDR_BRIGHTNESS",
        "description": "HDR 字幕亮度（0.0-1.0）",
        "min": 0.0,
        "max": 1.0,
    },
}


_config_manager: "ConfigManager | None" = None


def get_config(key: str):
    """Read a config value from ConfigManager at runtime."""
    if _config_manager is not None:
        value, _source = _config_manager.get(key)
        return value
    schema_entry = CONFIG_SCHEMA.get(key)
    if schema_entry is not None:
        return schema_entry["default"]
    raise KeyError(f"Unknown config key: {key}")


def init_config_manager(schema: dict = CONFIG_SCHEMA, yaml_path: str | Path = None) -> "ConfigManager":
    """Initialize the module-level ConfigManager. Called once by main.py at startup."""
    global _config_manager
    _config_manager = ConfigManager(schema=schema, yaml_path=yaml_path)
    return _config_manager


class ConfigManager:
    def __init__(self, schema: dict, yaml_path: str):
        self._schema = schema
        self._yaml_path = Path(yaml_path)
        self._yaml_data: dict = {}
        self._load_yaml()

    def _load_yaml(self):
        if self._yaml_path.exists():
            with open(self._yaml_path, 'r', encoding='utf-8') as f:
                self._yaml_data = yaml.safe_load(f) or {}
        else:
            self._yaml_data = {}

    def _save_yaml(self):
        self._yaml_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to temp file, then rename
        fd, tmp_path = tempfile.mkstemp(dir=self._yaml_path.parent, suffix='.yaml.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                yaml.dump(self._yaml_data, f, allow_unicode=True, default_flow_style=False)
            os.replace(tmp_path, self._yaml_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _cast_value(self, value, target_type):
        if value is None:
            return None
        if target_type == "boolean":
            if isinstance(value, bool):
                return value
            return str(value).lower() in ("true", "1", "yes")
        if target_type == "integer":
            return int(value)
        if target_type == "float":
            return float(value)
        return str(value)

    def _get_env_raw(self, key: str):
        schema = self._schema[key]
        env_var = schema.get("env_var")
        if env_var and env_var in os.environ:
            return os.environ[env_var]
        return None

    def get(self, key: str) -> tuple[Any, str]:
        if key not in self._schema:
            raise KeyError(f"Unknown config key: {key}")
        schema = self._schema[key]

        # 1. Check YAML
        if key in self._yaml_data:
            return self._cast_value(self._yaml_data[key], schema["type"]), "yaml"

        # 2. Check env var
        env_raw = self._get_env_raw(key)
        if env_raw is not None:
            return self._cast_value(env_raw, schema["type"]), "env"

        # 3. Default
        return schema["default"], "default"

    def set(self, key: str, value: Any) -> tuple[Any, str, Any, str]:
        old_value, old_source = self.get(key)
        if key not in self._schema:
            raise KeyError(f"Unknown config key: {key}")

        # No change → skip write
        if value == old_value:
            return old_value, old_source, old_value, old_source

        default_val = self._schema[key]["default"]
        env_raw = self._get_env_raw(key)
        env_val = self._cast_value(env_raw, self._schema[key]["type"]) if env_raw is not None else None

        # If value equals default and no env var override, remove from YAML
        if value == default_val and (env_val is None or value == env_val):
            self._yaml_data.pop(key, None)
        else:
            self._yaml_data[key] = value

        self._save_yaml()
        new_value, new_source = self.get(key)
        return new_value, new_source, old_value, old_source

    def delete(self, key: str) -> tuple[Any, str]:
        if key not in self._schema:
            raise KeyError(f"Unknown config key: {key}")
        self._yaml_data.pop(key, None)
        self._save_yaml()
        return self.get(key)

    def get_all(self) -> dict:
        result = {}
        for key, schema in self._schema.items():
            value, source = self.get(key)
            entry = {
                "value": value,
                "source": source,
                "type": schema["type"],
                "description": schema.get("description", ""),
            }
            if schema["type"] == "enum":
                entry["enum_values"] = schema.get("enum_values", [])
            if "min" in schema:
                entry["min"] = schema["min"]
            if "max" in schema:
                entry["max"] = schema["max"]
            result[key] = entry
        return result
