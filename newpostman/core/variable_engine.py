from __future__ import annotations

import re

from newpostman.models.environment import EnvironmentModel


class MissingVariableError(ValueError):
    """Request 使用了目前 Environment 未定義的變數。"""


class VariableEngine:
    """以 Environment 變數解析文字中的雙大括號樣板。"""

    _pattern = re.compile(r"\{\{\s*([\w.-]+)\s*\}\}")

    def __init__(self, environment: EnvironmentModel | None = None) -> None:
        """建立變數解析器。

        Args:
            environment: 目前作用 Environment；None 表示沒有任何變數。
        """
        self._variables = environment.variables if environment is not None else {}

    def render(self, text: str) -> str:
        """替換字串中的 Environment 變數。

        Args:
            text: 可能包含 `{{variable_name}}` 的輸入字串。

        Returns:
            已完成變數替換的字串。

        Raises:
            MissingVariableError: 樣板引用了未定義的變數。
        """

        def replace(match: re.Match[str]) -> str:
            variable_name = match.group(1)
            if variable_name not in self._variables:
                raise MissingVariableError(f"未定義變數：{{{{{variable_name}}}}}")
            return self._variables[variable_name]

        return self._pattern.sub(replace, text)
