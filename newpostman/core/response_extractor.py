from __future__ import annotations

import json
import re
from typing import Any

from jsonpath_ng.exceptions import JSONPathError, JsonPathLexerError, JsonPathParserError
from jsonpath_ng.ext import parse as parse_jsonpath

from newpostman.models.request import ExtractorModel, ExtractorType


class ResponseExtractor:
    """依 Request 設定從 Response Body 萃取 Runtime variable。"""

    def extract(
        self,
        body_text: str,
        extractors: list[ExtractorModel],
        runtime_variables: dict[str, str],
    ) -> list[str]:
        """套用所有 Extractor，回傳警告且不覆寫失敗目標的既有值。

        Args:
            body_text: HTTP Response 的文字本文。
            extractors: 依序套用的萃取設定。
            runtime_variables: 本次 RunContext 共用的執行期變數。

        Returns:
            各 Extractor 解析失敗或未匹配時的警告訊息。
        """
        warnings: list[str] = []
        parsed_json: Any | None = None
        json_parsed = False
        json_error: str | None = None

        for extractor in extractors:
            try:
                if extractor.kind is ExtractorType.JSONPATH:
                    if not json_parsed:
                        json_parsed = True
                        try:
                            parsed_json = json.loads(body_text)
                        except json.JSONDecodeError as exc:
                            json_error = f"Response 不是有效 JSON：{exc.msg}"
                    if json_error is not None:
                        warnings.append(
                            f"Extractor {extractor.variable_name}：{json_error}"
                        )
                        continue
                    matches = parse_jsonpath(extractor.expression).find(parsed_json)
                    if not matches:
                        warnings.append(
                            f"Extractor {extractor.variable_name}：JSONPath 未匹配任何值。"
                        )
                        continue
                    value = matches[0].value
                    runtime_variables[extractor.variable_name] = self._as_text(value)
                else:
                    match = re.search(extractor.expression, body_text)
                    if match is None:
                        warnings.append(
                            f"Extractor {extractor.variable_name}：Regex 未匹配。"
                        )
                        continue
                    try:
                        value = match.group(extractor.group_index)
                    except IndexError:
                        warnings.append(
                            f"Extractor {extractor.variable_name}：Regex 捕獲群組 "
                            f"{extractor.group_index} 不存在。"
                        )
                        continue
                    if value is None:
                        warnings.append(
                            f"Extractor {extractor.variable_name}：Regex 捕獲群組 "
                            f"{extractor.group_index} 未參與此次匹配。"
                        )
                        continue
                    runtime_variables[extractor.variable_name] = value
            except (JSONPathError, JsonPathLexerError, JsonPathParserError) as exc:
                warnings.append(
                    f"Extractor {extractor.variable_name}：JSONPath 解析失敗：{exc}"
                )
            except re.error as exc:
                warnings.append(
                    f"Extractor {extractor.variable_name}：Regex 格式錯誤：{exc}"
                )
        return warnings

    @staticmethod
    def _as_text(value: Any) -> str:
        """將 JSONPath 的值轉成可供文字樣板替換的字串。"""
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
