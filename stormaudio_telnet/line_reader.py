from __future__ import annotations


class TokenizedLine:
    """Represents a line of tokenized data."""

    def __init__(
        self,
        line: str
    ):
        self._line: str = line
        self._field_tokens: list[str | list(str)] = None

        remaining_line: str = line
        bracket_start_idx: int = line.find('[')
        bracket_end_idx: int = line.rfind(']')
        bracket_field_token: str = None
        if bracket_start_idx != -1 and bracket_end_idx != -1:
            # drop the brackets
            inner_token_start_idx = bracket_start_idx + 1
            inner_token_end_idx = bracket_end_idx
            bracket_field_token = line[inner_token_start_idx: inner_token_end_idx]
            # back off one character to account for the dot before the opening bracket
            remaining_line = line[0: bracket_start_idx - 1]
        self._field_tokens = remaining_line.split('.')
        if bracket_field_token is not None:
            bracket_field_tokens: list[str] = bracket_field_token.split(', ')
            self._field_tokens.append(bracket_field_tokens)

    def get_raw_line(
        self
    ) -> str:
        return self._line

    def get_field_tokens(
        self
    ) -> list[str | list(str)]:
        return self._field_tokens


class TokenizedLineReader:
    """Represents an accessor for a line of tokenized data;
    tokens can be popped sequentially."""

    def __init__(
        self,
        line: TokenizedLine
    ):
        self._line: TokenizedLine = line
        self._next_token_idx: int = None
        if len(self._line.get_field_tokens()) > 0:
            self._next_token_idx = 0

    def get_raw_line(
        self
    ) -> str:
        return self._line.get_raw_line()

    def pop_next_tokens_if_equal(
        self,
        expected: list(str | list(str))
    ) -> bool:
        popped_count: int = 0
        for expected_element in expected:
            if self.pop_next_token_if_equal(expected_element):
                popped_count += 1
            else:
                self._next_token_idx -= popped_count
                return False
        return True

    def pop_next_token_if_equal(
        self,
        expected: str | list(str)
    ) -> bool:
        if self._next_token_idx is not None and self._next_token_idx < len(self._line.get_field_tokens()):
            next_token = self._line.get_field_tokens()[self._next_token_idx]
            if next_token == expected:
                self._next_token_idx += 1
                return True
        return False

    def pop_next_token(
        self
    ) -> str | list(str):
        if self._next_token_idx is not None and self._next_token_idx < len(self._line.get_field_tokens()):
            next_token = self._line.get_field_tokens()[self._next_token_idx]
            self._next_token_idx += 1
            return next_token
        return None


class TokenizedLinesReader:
    """Represents unconsumed lines of tokenized data;
    allows observing and consuming the lines."""

    def __init__(
        self
    ):
        self._lines: list[TokenizedLine] = []
        self._next_line_idx: int = None
        self._saved_next_line_idx: int = None

    def has_next_line(
        self
    ) -> bool:
        return self._next_line_idx is not None and self._next_line_idx < len(self._lines)

    def add_lines(
        self,
        lines: list[str]
    ) -> None:
        for line in lines:
            self._lines.append(TokenizedLine(line))
        if self._next_line_idx is None and len(self._lines) > 0:
            self._next_line_idx = 0
            self._saved_next_line_idx = 0

    def read_next_line(
        self
    ) -> TokenizedLineReader:
        if self._next_line_idx is None or self._next_line_idx == len(self._lines):
            return None
        next_line = self._lines[self._next_line_idx]
        self._next_line_idx += 1
        return TokenizedLineReader(next_line)

    def consume_read_lines(
        self
    ) -> None:
        if self._next_line_idx == len(self._lines):
            self._next_line_idx = None
            self._saved_next_line_idx = None
            self._lines = []
        else:
            self._saved_next_line_idx = self._next_line_idx

    def reset_read_lines(
        self
    ) -> None:
        self._next_line_idx = self._saved_next_line_idx
