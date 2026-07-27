"""Safe final-message templates for confirmed invitation plans."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

FINAL_TEMPLATE_MAX_LENGTH: Final = 1000
FINAL_TEMPLATE_VARIABLES: Final[tuple[str, ...]] = (
    "author",
    "recipient",
    "date",
    "time",
    "place",
    "activity",
)
DEFAULT_FINAL_TEXT_TEMPLATE: Final = (
    "{recipient}, жду тебя {date} в {time}. Встречаемся в {place}, а дальше нас ждёт {activity} 💘"
)


class FinalTemplateValidationError(ValueError):
    """Describe a template that cannot be rendered through the safe contract."""


@dataclass(frozen=True, slots=True)
class FinalTemplateToken:
    """One literal or variable token produced by the safe template parser."""

    kind: str
    value: str


def parse_final_text_template(template: str) -> tuple[FinalTemplateToken, ...]:
    """Parse only literal text, escaped braces, and allowed exact variables."""
    tokens: list[FinalTemplateToken] = []
    literal: list[str] = []
    index = 0

    def flush_literal() -> None:
        if literal:
            tokens.append(FinalTemplateToken("literal", "".join(literal)))
            literal.clear()

    while index < len(template):
        character = template[index]

        if character == "{":
            if index + 1 < len(template) and template[index + 1] == "{":
                literal.append("{")
                index += 2
                continue

            closing_index = template.find("}", index + 1)
            if closing_index == -1:
                raise FinalTemplateValidationError("Закрой фигурную скобку в шаблоне.")

            variable = template[index + 1 : closing_index]
            if not variable:
                raise FinalTemplateValidationError("Пустая переменная в шаблоне недопустима.")
            if "{" in variable:
                raise FinalTemplateValidationError("Вложенные фигурные скобки недопустимы.")
            if variable not in FINAL_TEMPLATE_VARIABLES:
                raise FinalTemplateValidationError(f"Переменная {{{variable}}} не поддерживается.")

            flush_literal()
            tokens.append(FinalTemplateToken("variable", variable))
            index = closing_index + 1
            continue

        if character == "}":
            if index + 1 < len(template) and template[index + 1] == "}":
                literal.append("}")
                index += 2
                continue
            raise FinalTemplateValidationError("Открывающая фигурная скобка отсутствует.")

        literal.append(character)
        index += 1

    flush_literal()
    return tuple(tokens)


def normalize_final_text_template(template: str) -> str:
    """Trim surrounding whitespace and validate the safe placeholder grammar."""
    normalized = template.strip()
    if not normalized:
        raise FinalTemplateValidationError("Финальный текст не может быть пустым.")
    if len(normalized) > FINAL_TEMPLATE_MAX_LENGTH:
        raise FinalTemplateValidationError(
            f"Финальный текст не может быть длиннее {FINAL_TEMPLATE_MAX_LENGTH} символов."
        )

    parse_final_text_template(normalized)
    return normalized


def render_final_text_template(
    template: str,
    values: Mapping[str, object],
) -> str:
    """Render a validated template without attribute access, indexing, or code execution."""
    normalized = normalize_final_text_template(template)
    tokens = parse_final_text_template(normalized)
    missing_variables = {
        token.value for token in tokens if token.kind == "variable" and token.value not in values
    }
    if missing_variables:
        missing = ", ".join(sorted(missing_variables))
        raise FinalTemplateValidationError(
            f"Для шаблона не переданы значения переменных: {missing}."
        )

    return "".join(
        str(values[token.value]) if token.kind == "variable" else token.value for token in tokens
    )
