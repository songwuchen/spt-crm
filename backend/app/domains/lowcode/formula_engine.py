"""
后端公式引擎 — 与前端 formulaParser.ts 对等实现

支持:
- 字段引用: $field_id#, $table.column#
- 四则运算: + - * / %  括号  一元负号
- 比较: == != > >= < <=
- 逻辑: && ||
- 字符串拼接: &
- 函数: 数学/日期/文本/逻辑/聚合/特殊
"""
from __future__ import annotations

import calendar
import math
import random
import re
import uuid as _uuid
from datetime import datetime, timedelta
from typing import Any


# ========== Tokenizer ==========

TOKEN_TYPES = (
    "NUMBER", "STRING", "FIELD_REF", "FUNC", "IDENT",
    "LPAREN", "RPAREN", "COMMA",
    "PLUS", "MINUS", "MUL", "DIV", "MOD",
    "EQ", "NE", "GT", "GTE", "LT", "LTE",
    "AND", "OR", "AMP",
    "EOF",
)


class Token:
    __slots__ = ("type", "value")

    def __init__(self, type_: str, value: str):
        self.type = type_
        self.value = value


def tokenize(src: str) -> list[Token]:
    tokens: list[Token] = []
    i, n = 0, len(src)

    while i < n:
        ch = src[i]

        # whitespace
        if ch in " \t\r\n":
            i += 1
            continue

        # comment /* ... */ (对齐简道云公式注释)
        if ch == '/' and i + 1 < n and src[i + 1] == '*':
            i += 2
            while i + 1 < n and not (src[i] == '*' and src[i + 1] == '/'):
                i += 1
            i += 2  # skip closing */
            continue

        # string literal
        if ch == '"':
            val, i = "", i + 1
            while i < n and src[i] != '"':
                val += src[i]
                i += 1
            i += 1  # closing "
            tokens.append(Token("STRING", val))
            continue

        # field reference $field_id# or $table.col#
        if ch == '$':
            ref, i = "", i + 1
            while i < n and (src[i].isalnum() or src[i] in "_." ):
                ref += src[i]
                i += 1
            if i < n and src[i] == '#':
                i += 1
            tokens.append(Token("FIELD_REF", ref))
            continue

        # number
        if ch.isdigit() or (ch == '.' and i + 1 < n and src[i + 1].isdigit()):
            num = ""
            while i < n and (src[i].isdigit() or src[i] == '.'):
                num += src[i]
                i += 1
            tokens.append(Token("NUMBER", num))
            continue

        # identifier / function name
        if ch.isalpha() or ch == '_':
            ident = ""
            while i < n and (src[i].isalnum() or src[i] == '_'):
                ident += src[i]
                i += 1
            if i < n and src[i] == '(':
                tokens.append(Token("FUNC", ident.upper()))
            else:
                tokens.append(Token("IDENT", ident))
            continue

        # two-char operators
        two = src[i:i + 2]
        two_map = {"==": "EQ", "!=": "NE", ">=": "GTE", "<=": "LTE", "&&": "AND", "||": "OR"}
        if two in two_map:
            tokens.append(Token(two_map[two], two))
            i += 2
            continue

        # single-char operators
        one_map = {
            '(': "LPAREN", ')': "RPAREN", ',': "COMMA",
            '+': "PLUS", '-': "MINUS", '*': "MUL", '/': "DIV", '%': "MOD",
            '>': "GT", '<': "LT", '&': "AMP",
        }
        if ch in one_map:
            tokens.append(Token(one_map[ch], ch))
            i += 1
            continue

        # skip unknown
        i += 1

    tokens.append(Token("EOF", ""))
    return tokens


# ========== Helper conversions ==========

def _to_num(v: Any) -> float:
    if v is None:
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return 0.0 if isinstance(v, float) and math.isnan(v) else float(v)
    if isinstance(v, (list, tuple)):
        return 0.0
    try:
        return float(str(v))
    except (ValueError, TypeError):
        return 0.0


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    # 整数值的浮点数去掉 .0(与前端 JS 数字字符串化一致,如 CONCATENATE 拼接 2+2 → "4" 而非 "4.0");
    # 不限大小,规避大整数被 str(float) 变成科学计数法(如 1e+22)
    if isinstance(v, float) and not (math.isinf(v) or math.isnan(v)) and v.is_integer():
        return str(int(v))
    if isinstance(v, (list, tuple)):
        return ",".join(_to_str(x) for x in v)
    return str(v)


def _to_bool(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v != "" and v != "0" and v.lower() != "false"
    if isinstance(v, (list, tuple)):
        return len(v) > 0
    return False


def _as_list(v: Any) -> list:
    """把参数规整为列表:数组原样,标量包成单元素列表(供聚合类函数展开)。"""
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v]


def _num_list(args: list[Any]) -> list[float]:
    """展开参数为数字列表:数组参数逐元素展开(对齐简道云 SUM/AVG 可传数组)。"""
    out: list[float] = []
    for a in args:
        if isinstance(a, (list, tuple)):
            out.extend(_to_num(x) for x in a)
        else:
            out.append(_to_num(a))
    return out


def _match_criteria(value: Any, criteria: str) -> bool:
    """判断值是否满足条件表达式,如 ">2" / ">=50" / "!=0" / "苹果"(精确匹配)。"""
    c = criteria.strip()
    for op in (">=", "<=", "!=", "<>", ">", "<", "="):
        if c.startswith(op):
            rest = c[len(op):].strip()
            try:
                target = float(rest)
                num = _to_num(value)
                if op == ">=":
                    return num >= target
                if op == "<=":
                    return num <= target
                if op in ("!=", "<>"):
                    return num != target
                if op == ">":
                    return num > target
                if op == "<":
                    return num < target
                return num == target
            except ValueError:
                sv = _to_str(value)
                if op in ("!=", "<>"):
                    return sv != rest
                if op == "=":
                    return sv == rest
                return False
    return _to_str(value) == c


def _parse_date(s: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ========== Parser ==========

class Parser:
    def __init__(self, tokens: list[Token], values: dict[str, Any]):
        self.tokens = tokens
        self.pos = 0
        self.values = values

    def _peek(self) -> Token:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else Token("EOF", "")

    def _advance(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def _expect(self, type_: str) -> Token:
        t = self._advance()
        if t.type != type_:
            raise ValueError(f"Expected {type_}, got {t.type}")
        return t

    def parse(self) -> Any:
        return self._expr()

    def _expr(self) -> Any:
        return self._or_expr()

    def _or_expr(self) -> Any:
        left = self._and_expr()
        while self._peek().type == "OR":
            self._advance()
            right = self._and_expr()
            left = _to_bool(left) or _to_bool(right)
        return left

    def _and_expr(self) -> Any:
        left = self._compare()
        while self._peek().type == "AND":
            self._advance()
            right = self._compare()
            left = _to_bool(left) and _to_bool(right)
        return left

    def _compare(self) -> Any:
        left = self._add()
        t = self._peek().type
        if t in ("EQ", "NE", "GT", "GTE", "LT", "LTE"):
            self._advance()
            right = self._add()
            l, r = _to_num(left), _to_num(right)
            ls, rs = _to_str(left), _to_str(right)
            if t == "EQ":
                return ls == rs or l == r
            if t == "NE":
                return ls != rs and l != r
            if t == "GT":
                return l > r
            if t == "GTE":
                return l >= r
            if t == "LT":
                return l < r
            if t == "LTE":
                return l <= r
        return left

    def _add(self) -> Any:
        left = self._mul()
        while True:
            t = self._peek().type
            if t == "PLUS":
                self._advance()
                left = _to_num(left) + _to_num(self._mul())
            elif t == "MINUS":
                self._advance()
                left = _to_num(left) - _to_num(self._mul())
            elif t == "AMP":
                self._advance()
                left = _to_str(left) + _to_str(self._mul())
            else:
                break
        return left

    def _mul(self) -> Any:
        left = self._unary()
        while True:
            t = self._peek().type
            if t == "MUL":
                self._advance()
                left = _to_num(left) * _to_num(self._unary())
            elif t == "DIV":
                self._advance()
                r = _to_num(self._unary())
                left = 0 if r == 0 else _to_num(left) / r
            elif t == "MOD":
                self._advance()
                r = _to_num(self._unary())
                left = 0 if r == 0 else _to_num(left) % r
            else:
                break
        return left

    def _unary(self) -> Any:
        if self._peek().type == "MINUS":
            self._advance()
            return -_to_num(self._unary())
        return self._primary()

    def _primary(self) -> Any:
        t = self._peek()

        if t.type == "NUMBER":
            self._advance()
            return float(t.value)
        if t.type == "STRING":
            self._advance()
            return t.value
        if t.type == "FIELD_REF":
            self._advance()
            return self._resolve_field(t.value)
        if t.type == "IDENT":
            self._advance()
            upper = t.value.upper()
            if upper == "TRUE":
                return True
            if upper == "FALSE":
                return False
            if upper == "NULL":
                return None
            return t.value
        if t.type == "FUNC":
            return self._func_call()
        if t.type == "LPAREN":
            self._advance()
            val = self._expr()
            self._expect("RPAREN")
            return val

        self._advance()
        return None

    def _resolve_field(self, path: str) -> Any:
        parts = path.split(".")
        current: Any = self.values
        for p in parts:
            if current is None or not isinstance(current, dict):
                return None
            current = current.get(p)
        if current is None:
            return None
        if isinstance(current, bool):
            return current
        if isinstance(current, (int, float)):
            return current
        if isinstance(current, str):
            s = current.strip()
            # 超大整数(超出 JS 安全整数范围)用 int 保精度:str(int) 不会科学计数,
            # 对齐前端保留用户输入的完整长数字(& 拼接 / CONCATENATE / TEXT)
            if re.fullmatch(r"-?\d+", s):
                iv = int(s)
                if abs(iv) > 9007199254740991:  # 2**53 - 1
                    return iv
            try:
                return float(current)
            except ValueError:
                return current
        if isinstance(current, list):
            # 多值字段(成员多选/复选组等)以数组透传,供 JOIN/INDEX/COUNT 等使用
            return current
        return None

    def _func_call(self) -> Any:
        name = self._advance().value
        self._expect("LPAREN")
        args = self._parse_args()
        self._expect("RPAREN")
        return self._eval_func(name, args)

    def _parse_args(self) -> list[Any]:
        args: list[Any] = []
        if self._peek().type == "RPAREN":
            return args
        args.append(self._expr())
        while self._peek().type == "COMMA":
            self._advance()
            args.append(self._expr())
        return args

    def _eval_func(self, name: str, args: list[Any]) -> Any:
        # ================= 逻辑函数 =================
        if name == "IF":
            return args[1] if _to_bool(args[0]) else (args[2] if len(args) > 2 else None)
        if name == "IFS":
            # IFS(条件1,值1,条件2,值2,...):返回首个成立条件对应的值,均不成立返回 None
            for i in range(0, len(args) - 1, 2):
                if _to_bool(args[i]):
                    return args[i + 1]
            return None
        if name == "AND":
            return all(_to_bool(a) for a in args) if args else False
        if name == "OR":
            return any(_to_bool(a) for a in args)
        if name == "NOT":
            return not _to_bool(args[0] if args else None)
        if name == "XOR":
            return sum(1 for a in args if _to_bool(a)) % 2 == 1
        if name == "TRUE":
            return True
        if name == "FALSE":
            return False

        # ================= 文本函数 =================
        if name in ("CONCATENATE", "CONCAT"):
            return "".join(_to_str(a) for a in args)
        if name == "CHAR":
            m = {9: "\t", 10: "\n", 34: '"', 39: "'", 92: "\\"}
            n = int(_to_num(args[0])) if args else 0
            return m.get(n, chr(n) if 0 <= n <= 0x10FFFF else "")
        if name == "EXACT":
            return _to_str(args[0]) == _to_str(args[1])
        if name == "ISEMPTY":
            v = args[0] if args else None
            return (
                v is None or v == "" or v == []
                or (isinstance(v, float) and math.isnan(v))
            )
        if name == "JOIN":
            if args and isinstance(args[0], (list, tuple)):
                items = list(args[0])
                sep = _to_str(args[1]) if len(args) > 1 else ""
            else:
                sep = _to_str(args[-1]) if args else ""
                items = args[:-1]
            return sep.join(_to_str(x) for x in items)
        if name == "LEFT":
            n = int(_to_num(args[1])) if len(args) > 1 else 1
            return _to_str(args[0])[:max(0, n)]
        if name == "LEN":
            return len(_to_str(args[0]))
        if name == "LOWER":
            return _to_str(args[0]).lower()
        if name == "MID":
            s = _to_str(args[0])
            start = max(0, (int(_to_num(args[1])) if len(args) > 1 else 1) - 1)  # 1-based
            length = int(_to_num(args[2])) if len(args) > 2 else 1
            return s[start:start + length]
        if name == "REPLACE":
            text = _to_str(args[0])
            start = max(0, int(_to_num(args[1])) - 1)
            length = int(_to_num(args[2]))
            new_text = _to_str(args[3]) if len(args) > 3 else ""
            return text[:start] + new_text + text[start + length:]
        if name == "REPT":
            return _to_str(args[0]) * max(0, int(_to_num(args[1])))
        if name == "RIGHT":
            n = int(_to_num(args[1])) if len(args) > 1 else 1
            return _to_str(args[0])[-n:] if n > 0 else ""
        if name == "RMBCAP":
            return _rmbcap(_to_num(args[0]))
        if name == "SEARCH":
            find = _to_str(args[0]).lower()
            text = _to_str(args[1]).lower()
            start = max(0, int(_to_num(args[2])) - 1) if len(args) > 2 else 0
            idx = text.find(find, start)
            return idx + 1 if idx >= 0 else 0
        if name == "SPLIT":
            sep = _to_str(args[1]) if len(args) > 1 else ""
            return _to_str(args[0]).split(sep) if sep else list(_to_str(args[0]))
        if name == "TRIM":
            return _to_str(args[0]).strip()
        if name == "TEXT":
            fmt = _to_str(args[1]) if len(args) > 1 else "0.00"
            if re.search(r"[yMdHsE]", fmt):
                dt = _parse_date(_to_str(args[0]))
                if dt:
                    return _jdy_date_fmt(dt, fmt)
            # 精确整数(如文本/数字字段里的长数字)按原始数字串格式化,避免 float 丢精度/科学计数法
            raw = args[0]
            int_str = None
            if isinstance(raw, bool):
                pass
            elif isinstance(raw, int):
                int_str = str(raw)
            elif isinstance(raw, str) and re.fullmatch(r"-?\d+", raw.strip()):
                int_str = raw.strip()
            if int_str is not None:
                return _format_int_str(int_str.startswith("-"), int_str.lstrip("-"), fmt)
            return _text_number(_to_num(raw), fmt)
        if name == "UPPER":
            return _to_str(args[0]).upper()
        if name == "UNION":
            seen: list = []
            for a in args:
                for x in (a if isinstance(a, (list, tuple)) else [a]):
                    if x not in seen:
                        seen.append(x)
            return seen
        if name == "VALUE":
            try:
                return float(_to_str(args[0]))
            except ValueError:
                return 0
        if name == "IP":
            return _to_str(self.values.get("__clientIp__", ""))

        # ================= 数学函数 =================
        if name == "ABS":
            return abs(_to_num(args[0]))
        if name in ("AVERAGE", "AVG"):
            nums = _num_list(args)
            return sum(nums) / len(nums) if nums else 0
        if name in ("CEILING", "CEIL"):
            sig = _to_num(args[1]) if len(args) > 1 else 1
            return 0 if sig == 0 else math.ceil(_to_num(args[0]) / sig) * sig
        if name == "COS":
            return math.cos(_to_num(args[0]))
        if name == "COT":
            t = math.tan(_to_num(args[0]))
            return 0 if t == 0 else 1 / t
        if name == "COUNT":
            return sum(1 for x in _flat_all(args) if x not in (None, ""))
        if name == "COUNTIF":
            if len(args) >= 2 and isinstance(args[0], (list, tuple)):
                items, crit = list(args[0]), _to_str(args[1])
            else:
                items, crit = _flat_all(args[:-1]), _to_str(args[-1]) if args else ""
            return sum(1 for x in items if _match_criteria(x, crit))
        if name in ("FLOOR",):
            sig = _to_num(args[1]) if len(args) > 1 else 1
            return 0 if sig == 0 else math.floor(_to_num(args[0]) / sig) * sig
        if name == "FIXED":
            num = _to_num(args[0])
            dec = int(_to_num(args[1])) if len(args) > 1 else 2
            no_commas = _to_bool(args[2]) if len(args) > 2 else False
            fixed = f"{num:.{max(0, dec)}f}"
            if no_commas:
                return fixed
            parts = fixed.split(".")
            int_part = parts[0]
            if int_part.startswith("-"):
                int_part = "-" + _add_commas(int_part[1:])
            else:
                int_part = _add_commas(int_part)
            return f"{int_part}.{parts[1]}" if len(parts) > 1 else int_part
        if name == "INT":
            return math.floor(_to_num(args[0]))
        if name == "LARGE":
            nums = sorted(_num_list([args[0]]), reverse=True)
            k = int(_to_num(args[1])) if len(args) > 1 else 1
            return nums[k - 1] if 1 <= k <= len(nums) else 0
        if name == "LOG":
            v = _to_num(args[0])
            if v <= 0:
                return 0
            if len(args) >= 2:
                base = _to_num(args[1])
                return math.log(v) / math.log(base) if base > 0 and base != 1 else 0
            return math.log(v)
        if name == "MOD":
            b = _to_num(args[1])
            return 0 if b == 0 else _to_num(args[0]) % b
        if name == "MAX":
            nums = _num_list(args)
            return max(nums) if nums else 0
        if name == "MIN":
            nums = _num_list(args)
            return min(nums) if nums else 0
        if name == "POWER":
            return math.pow(_to_num(args[0]), _to_num(args[1]))
        if name == "PRODUCT":
            nums = _num_list(args)
            r = 1.0
            for x in nums:
                r *= x
            return r if nums else 0
        if name == "RADIANS":
            return math.radians(_to_num(args[0]))
        if name == "RAND":
            return random.random()
        if name == "ROUND":
            decimals = int(_to_num(args[1])) if len(args) > 1 else 0
            return round(_to_num(args[0]), decimals)
        if name == "SIN":
            return math.sin(_to_num(args[0]))
        if name == "SMALL":
            nums = sorted(_num_list([args[0]]))
            k = int(_to_num(args[1])) if len(args) > 1 else 1
            return nums[k - 1] if 1 <= k <= len(nums) else 0
        if name == "SQRT":
            return math.sqrt(max(0, _to_num(args[0])))
        if name == "SUM":
            return sum(_num_list(args))
        if name == "SUMIF":
            rng = _as_list(args[0])
            crit = _to_str(args[1]) if len(args) > 1 else ""
            sr = _as_list(args[2]) if len(args) > 2 else rng
            return sum(_to_num(sr[i]) for i in range(len(rng))
                       if i < len(sr) and _match_criteria(rng[i], crit))
        if name == "SUMIFS":
            sr = _as_list(args[0])
            pairs = [(_as_list(args[i]), _to_str(args[i + 1])) for i in range(1, len(args) - 1, 2)]
            total = 0.0
            for i in range(len(sr)):
                if all(i < len(cr) and _match_criteria(cr[i], c) for cr, c in pairs):
                    total += _to_num(sr[i])
            return total
        if name == "SUMPRODUCT":
            arrs = [_as_list(a) for a in args]
            if not arrs:
                return 0
            length = min(len(a) for a in arrs)
            total = 0.0
            for i in range(length):
                p = 1.0
                for a in arrs:
                    p *= _to_num(a[i])
                total += p
            return total
        if name == "TAN":
            return math.tan(_to_num(args[0]))

        # ================= 日期函数 =================
        if name == "NOW":
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if name == "SYSTIME":
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if name == "TODAY":
            return datetime.now().strftime("%Y-%m-%d")
        if name == "YEAR":
            dt = _parse_date(_to_str(args[0])) if args else None
            return dt.year if dt else None
        if name == "MONTH":
            dt = _parse_date(_to_str(args[0])) if args else None
            return dt.month if dt else None
        if name == "DAY":
            dt = _parse_date(_to_str(args[0])) if args else None
            return dt.day if dt else None
        if name == "HOUR":
            dt = _parse_date(_to_str(args[0])) if args else None
            return dt.hour if dt else None
        if name == "MINUTE":
            dt = _parse_date(_to_str(args[0])) if args else None
            return dt.minute if dt else None
        if name == "SECOND":
            dt = _parse_date(_to_str(args[0])) if args else None
            return dt.second if dt else None
        if name == "DATE":
            y, m, d = int(_to_num(args[0])), int(_to_num(args[1])), int(_to_num(args[2]))
            hh = int(_to_num(args[3])) if len(args) > 3 else 0
            mm = int(_to_num(args[4])) if len(args) > 4 else 0
            ss = int(_to_num(args[5])) if len(args) > 5 else 0
            try:
                dt = datetime(y, m, d, hh, mm, ss)
                return dt.strftime("%Y-%m-%d %H:%M:%S") if len(args) > 3 else dt.strftime("%Y-%m-%d")
            except ValueError:
                return None
        if name == "TIME":
            h, m, s = _to_num(args[0]), _to_num(args[1]) if len(args) > 1 else 0, _to_num(args[2]) if len(args) > 2 else 0
            return (h * 3600 + m * 60 + s) / 86400
        if name == "TIMESTAMP":
            dt = _parse_date(_to_str(args[0])) if args else None
            return int(dt.timestamp() * 1000) if dt else None
        if name == "DATEDIF":
            s = _parse_date(_to_str(args[0]))
            e = _parse_date(_to_str(args[1]))
            if not s or not e:
                return 0
            u = _to_str(args[2]) if len(args) > 2 else "d"
            if u == "M":
                return (e.year - s.year) * 12 + (e.month - s.month)
            if u == "y":
                return e.year - s.year
            diff = (e - s).total_seconds()
            if u == "h":
                return round(diff / 3600, 2)
            if u == "m":
                return round(diff / 60, 2)
            return int(diff // 86400)
        if name == "DAYS":
            e = _parse_date(_to_str(args[0]))
            s = _parse_date(_to_str(args[1]))
            return int((e - s).total_seconds() // 86400) if s and e else 0
        if name == "DAYS360":
            e = _parse_date(_to_str(args[0]))
            s = _parse_date(_to_str(args[1]))
            return _days360(s, e) if s and e else 0
        if name in ("DATEDELTA", "DATEADD"):
            dt = _parse_date(_to_str(args[0]))
            if not dt:
                return None
            n = _to_num(args[1]) if len(args) > 1 else 0
            u = _to_str(args[2]) if len(args) > 2 else "d"  # DATEDELTA 恒为天
            unit_map = {"d": "days", "h": "hours", "m": "minutes", "w": "weeks"}
            if u in unit_map:
                dt = dt + timedelta(**{unit_map[u]: n})
            elif u == "M":
                new_month = dt.month + int(n)
                new_year = dt.year + (new_month - 1) // 12
                new_month = (new_month - 1) % 12 + 1
                last_day = calendar.monthrange(new_year, new_month)[1]
                dt = dt.replace(year=new_year, month=new_month, day=min(dt.day, last_day))
            elif u == "y":
                try:
                    dt = dt.replace(year=dt.year + int(n))
                except ValueError:
                    dt = dt.replace(year=dt.year + int(n), day=28)
            fmt = "%Y-%m-%d %H:%M:%S" if u in ("h", "m") else "%Y-%m-%d"
            return dt.strftime(fmt)
        if name == "WEEKDAY":
            dt = _parse_date(_to_str(args[0])) if args else None
            if not dt:
                return None
            return dt.isoweekday() % 7  # 0=周日 ... 6=周六(对齐简道云)
        if name == "WEEKNUM":
            dt = _parse_date(_to_str(args[0])) if args else None
            return dt.isocalendar()[1] if dt else None
        if name == "ISOWEEKNUM":
            dt = _parse_date(_to_str(args[0])) if args else None
            return dt.isocalendar()[1] if dt else None
        if name == "NETWORKDAYS":
            s = _parse_date(_to_str(args[0]))
            e = _parse_date(_to_str(args[1]))
            hol = _holiday_set(args[2]) if len(args) > 2 else set()
            return _networkdays(s, e, hol) if s and e else 0
        if name == "WORKDAY":
            s = _parse_date(_to_str(args[0]))
            n = int(_to_num(args[1])) if len(args) > 1 else 0
            hol = _holiday_set(args[2]) if len(args) > 2 else set()
            dt = _workday(s, n, hol) if s else None
            return dt.strftime("%Y-%m-%d") if dt else None

        # ================= 高级函数 =================
        if name == "RECNO":
            return _to_num(self.values.get("__rowIndex__", 0))
        if name == "GETUSERNAME":
            return _to_str(self.values.get("__currentUser__", ""))
        if name == "UUID":
            return str(_uuid.UUID(int=random.getrandbits(128)))
        if name == "INDEX":
            arr = _as_list(args[0]) if args else []
            pos = int(_to_num(args[1])) if len(args) > 1 else 1
            return arr[pos - 1] if 1 <= pos <= len(arr) else None

        # ---- 明细聚合兜底(正常已由预处理替换) ----
        if name == "SUBTOTAL":
            return _to_num(args[1]) if len(args) >= 2 else 0

        return None


def _add_commas(s: str) -> str:
    result = ""
    for i, ch in enumerate(reversed(s)):
        if i > 0 and i % 3 == 0:
            result = "," + result
        result = ch + result
    return result


def _flat_all(args: list[Any]) -> list:
    """展开参数为一维列表(数组参数逐元素展开,保留原始类型)。"""
    out: list = []
    for a in args:
        if isinstance(a, (list, tuple)):
            out.extend(a)
        else:
            out.append(a)
    return out


_RMB_DIGITS = "零壹贰叁肆伍陆柒捌玖"


def _rmbcap(n: float) -> str:
    """金额小写转人民币大写(对齐简道云 RMBCAP)。"""
    if not n:
        return "零元整"
    neg = n < 0
    n = abs(round(n + 1e-9, 2))
    int_part = int(n)
    frac = int(round((n - int_part) * 100))
    jiao, fen = frac // 10, frac % 10

    def int_to_cap(num: int) -> str:
        if num == 0:
            return ""
        units = ["", "拾", "佰", "仟"]
        groups = ["", "万", "亿", "兆"]
        s, g = "", 0
        while num > 0:
            part = num % 10000
            if part != 0:
                tmp, u, zero = "", 0, False
                p = part
                while p > 0:
                    d = p % 10
                    if d == 0:
                        if tmp:  # 仅在低位已有内容时,零才作为间隔零
                            zero = True
                    else:
                        if zero:
                            tmp = "零" + tmp
                            zero = False
                        tmp = _RMB_DIGITS[d] + units[u] + tmp
                    p //= 10
                    u += 1
                s = tmp + groups[g] + s
            elif s and not s.startswith("零"):
                s = "零" + s
            num //= 10000
            g += 1
        return s

    result = (int_to_cap(int_part) + "元") if int_part > 0 else ""
    if jiao == 0 and fen == 0:
        result += "整"
    else:
        if jiao > 0:
            result += _RMB_DIGITS[jiao] + "角"
        elif int_part > 0 and fen > 0:
            result += "零"
        if fen > 0:
            result += _RMB_DIGITS[fen] + "分"
    return ("负" if neg else "") + (result or "零元整")


def _jdy_date_fmt(dt: datetime, fmt: str) -> str:
    """把简道云日期格式(yyyy-MM-dd HH:mm:ss E)转为 strftime 输出。"""
    out, i, n = "", 0, len(fmt)
    tokens = [("yyyy", "%Y"), ("yy", "%y"), ("MM", "%m"), ("dd", "%d"),
              ("HH", "%H"), ("mm", "%M"), ("ss", "%S"), ("E", "%a")]
    while i < n:
        matched = False
        for jt, st in tokens:
            if fmt.startswith(jt, i):
                out += dt.strftime(st)
                i += len(jt)
                matched = True
                break
        if not matched:
            out += fmt[i]
            i += 1
    return out


def _text_number(v: float, fmt: str) -> str:
    """按简道云 TEXT 数字格式(#/0/./,/%)格式化。"""
    is_pct = "%" in fmt
    core = fmt.replace("%", "")
    frac_pat = core.split(".")[1] if "." in core else ""
    dec = len(frac_pat)
    val = v * 100 if is_pct else v
    s = f"{val:.{dec}f}"
    if "#" in frac_pat and "0" not in frac_pat and "." in s:
        s = s.rstrip("0").rstrip(".")
    if "," in core:
        neg = s.startswith("-")
        body = s[1:] if neg else s
        ip, _, fp = body.partition(".")
        ip = _add_commas(ip)
        s = ("-" if neg else "") + ip + (("." + fp) if fp else "")
    return s + ("%" if is_pct else "")


def _format_int_str(neg: bool, digits: str, fmt: str) -> str:
    """从精确整数(符号 + 数字串)按 TEXT 数字格式输出,避免 float 精度丢失与科学计数法。"""
    is_pct = "%" in fmt
    core = fmt.replace("%", "")
    frac_pat = core.split(".")[1] if "." in core else ""
    dec = len(frac_pat)
    d = digits.lstrip("0") or "0"
    if is_pct and d != "0":
        d = d + "00"
    s = d
    if dec > 0:
        s = s + "." + "0" * dec
    if "#" in frac_pat and "0" not in frac_pat and "." in s:
        s = s.rstrip("0").rstrip(".")
    if "," in core:
        ip, _, fp = s.partition(".")
        ip = _add_commas(ip)
        s = ip + (("." + fp) if fp else "")
    return ("-" if neg else "") + s + ("%" if is_pct else "")


def _days360(start: datetime, end: datetime) -> int:
    """美式 30/360 天数差(对齐简道云 DAYS360)。"""
    d1, d2 = start.day, end.day
    if d1 == 31:
        d1 = 30
    if d2 == 31 and d1 == 30:
        d2 = 30
    return (end.year - start.year) * 360 + (end.month - start.month) * 30 + (d2 - d1)


def _holiday_set(holidays: Any) -> set:
    out = set()
    for h in (holidays if isinstance(holidays, (list, tuple)) else [holidays]):
        dt = _parse_date(_to_str(h))
        if dt:
            out.add(dt.date())
    return out


def _networkdays(start: datetime, end: datetime, holidays: set) -> int:
    """两日期间工作日数(含首尾,排除周末与假日)。"""
    sign = 1
    if start > end:
        start, end, sign = end, start, -1
    days, cur = 0, start
    while cur.date() <= end.date():
        if cur.weekday() < 5 and cur.date() not in holidays:
            days += 1
        cur += timedelta(days=1)
    return days * sign


def _workday(start: datetime, n: int, holidays: set) -> datetime:
    """从 start 起顺(逆)推 n 个工作日后的日期。"""
    step = 1 if n >= 0 else -1
    remaining, cur = abs(n), start
    while remaining > 0:
        cur += timedelta(days=step)
        if cur.weekday() < 5 and cur.date() not in holidays:
            remaining -= 1
    return cur


# ========== Pre-processing ==========

_SUBTOTAL_RE = re.compile(
    r'SUBTOTAL\(\s*"([^"]+)"\s*,\s*\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\s*\)',
    re.IGNORECASE,
)

# SUM/AVG/COUNT/MAX/MIN($子表.列#) —— 聚合变量直接聚合明细列(对齐简道云 SUM(子表.列))
_MULTI_AGG_RE = re.compile(
    r'\b(SUM|AVG|AVERAGE|COUNT|MAX|MIN)\(\s*\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\s*\)',
    re.IGNORECASE,
)

_COUNTIF_RE = re.compile(
    r'COUNTIF\(\s*\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\s*,\s*"([^"]+)"\s*\)',
    re.IGNORECASE,
)

_SUMIF_RE = re.compile(
    r'SUMIF\(\s*\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\s*,\s*\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\s*,\s*"([^"]+)"\s*\)',
    re.IGNORECASE,
)

_TEXTLOCATION_RE = re.compile(
    r'TEXTLOCATION\(\s*\$([a-zA-Z0-9_]+)#\s*(?:,\s*"([^"]*)"\s*)?\)',
    re.IGNORECASE,
)

_DISTANCE_RE = re.compile(
    r'DISTANCE\(\s*\$([a-zA-Z0-9_]+)#\s*,\s*\$([a-zA-Z0-9_]+)#\s*\)',
    re.IGNORECASE,
)

# TEXTUSER($成员#, "name"|"username") / TEXTDEPT($部门#, "name"|"deptno") / TEXTPHONE($手机#, "phone"|"verified")
_TEXTUSER_RE = re.compile(
    r'TEXTUSER\(\s*\$([a-zA-Z0-9_]+)#\s*(?:,\s*"([^"]*)"\s*)?\)', re.IGNORECASE)
_TEXTDEPT_RE = re.compile(
    r'TEXTDEPT\(\s*\$([a-zA-Z0-9_]+)#\s*(?:,\s*"([^"]*)"\s*)?\)', re.IGNORECASE)
_TEXTPHONE_RE = re.compile(
    r'TEXTPHONE\(\s*\$([a-zA-Z0-9_]+)#\s*(?:,\s*"([^"]*)"\s*)?\)', re.IGNORECASE)

# MAPX("op", 匹配值, $匹配字段#, $返回字段#) —— 结果由异步上下文构造器预算好放进 __mapx__
_MAPX_RE = re.compile(
    r'MAPX\(\s*"([^"]+)"\s*,\s*(\$[a-zA-Z0-9_]+#|"[^"]*"|-?[0-9.]+)\s*,'
    r'\s*\$([a-zA-Z0-9_]+)#\s*,\s*\$([a-zA-Z0-9_]+)#\s*\)',
    re.IGNORECASE,
)


def _id_list(raw: Any) -> list[str]:
    """把成员/部门字段值规整为 id 字符串列表(兼容单值/数组/对象)。"""
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        out = []
        for x in raw:
            if isinstance(x, dict):
                v = x.get("id") or x.get("value") or x.get("key")
                if v:
                    out.append(str(v))
            elif x not in (None, ""):
                out.append(str(x))
        return out
    if isinstance(raw, dict):
        v = raw.get("id") or raw.get("value") or raw.get("key")
        return [str(v)] if v else []
    return [str(raw)]


def _text_user(raw: Any, fmt: str, user_map: dict) -> str:
    """按 __user_map__({id:{name,username}}) 解析成员字段为姓名/用户名。"""
    key = "username" if (fmt or "name").lower() == "username" else "name"
    parts = []
    for uid in _id_list(raw):
        info = user_map.get(uid) or user_map.get(str(uid)) or {}
        parts.append(str(info.get(key) or (uid if key == "username" else "")))
    return ",".join(p for p in parts if p)


def _text_dept(raw: Any, fmt: str, dept_map: dict) -> str:
    """按 __dept_map__({id:{name,deptno}}) 解析部门字段为部门名/部门编号。"""
    key = "deptno" if (fmt or "name").lower() == "deptno" else "name"
    parts = []
    for did in _id_list(raw):
        info = dept_map.get(did) or dept_map.get(str(did)) or {}
        parts.append(str(info.get(key) or (did if key == "deptno" else "")))
    return ",".join(p for p in parts if p)


def _distance_meters(v1: Any, v2: Any) -> float | None:
    """两个定位字段值的球面距离(米,Haversine),对齐简道云 DISTANCE。任一无坐标返回 None。"""
    import math
    if not isinstance(v1, dict) or not isinstance(v2, dict):
        return None
    try:
        lat1, lng1 = float(v1["latitude"]), float(v1["longitude"])
        lat2, lng2 = float(v2["latitude"]), float(v2["longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    r = 6371000.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _text_location(value: Any, fmt: str | None) -> str:
    """从地址字段值({region,regionLabels,detail})或定位字段值({address,province,city,...})
    提取指定部分(对齐简道云 TEXTLOCATION:address/province/city/district/detail/lng/lat)。"""
    if not isinstance(value, dict):
        return ""
    # 定位字段:结构化地址(逆地理组件) + 经纬度
    if isinstance(value.get("latitude"), (int, float)) or isinstance(value.get("longitude"), (int, float)):
        key = (fmt or "all").lower()

        def _s(k: str) -> str:
            v = value.get(k)
            return v if isinstance(v, str) else ""

        if key in ("all", "address"):
            return _s("address")
        if key == "province":
            return _s("province")
        if key == "city":
            return _s("city")
        if key == "district":
            return _s("district")
        if key == "detail":
            return _s("detail")
        if key in ("lng", "lon", "longitude"):
            lng = value.get("longitude")
            return str(lng) if isinstance(lng, (int, float)) else ""
        if key in ("lat", "latitude"):
            lat = value.get("latitude")
            return str(lat) if isinstance(lat, (int, float)) else ""
        return ""
    labels = value.get("regionLabels")
    labels = [str(x) for x in labels] if isinstance(labels, list) else []
    detail = value.get("detail")
    detail = detail if isinstance(detail, str) else ""
    key = (fmt or "all").lower()
    if key == "province":
        return labels[0] if len(labels) > 0 else ""
    if key == "city":
        return labels[1] if len(labels) > 1 else ""
    if key == "district":
        return labels[2] if len(labels) > 2 else ""
    if key == "detail":
        return detail
    return "".join(labels) + detail


def _eval_condition(value: float, cond_str: str) -> bool:
    """Evaluate simple condition like '>100', '>=50', '!=0', '=5'."""
    cond_str = cond_str.strip()
    for op, fn in [(">=", lambda a, b: a >= b), ("<=", lambda a, b: a <= b),
                   ("!=", lambda a, b: a != b), (">", lambda a, b: a > b),
                   ("<", lambda a, b: a < b), ("=", lambda a, b: a == b)]:
        if cond_str.startswith(op):
            try:
                target = float(cond_str[len(op):])
                return fn(value, target)
            except ValueError:
                return False
    # string exact match
    return str(value) == cond_str


def _preprocess(formula: str, values: dict[str, Any]) -> str:
    """Pre-process SUBTOTAL, COUNTIF, SUMIF before parsing."""

    def _subtotal_repl(m: re.Match) -> str:
        agg_type = m.group(1).lower()
        table_id = m.group(2)
        col_id = m.group(3)
        table_data = values.get(table_id)
        if not isinstance(table_data, list):
            return "0"
        col_values = [float(row.get(col_id, 0) or 0) for row in table_data if isinstance(row, dict)]
        if not col_values:
            return "0"
        if agg_type == "sum":
            return str(sum(col_values))
        if agg_type == "avg":
            return str(sum(col_values) / len(col_values))
        if agg_type == "count":
            return str(len(col_values))
        if agg_type == "max":
            return str(max(col_values))
        if agg_type == "min":
            return str(min(col_values))
        return "0"

    def _multi_agg_repl(m: re.Match) -> str:
        agg = m.group(1).lower()
        if agg == "average":
            agg = "avg"
        table_id, col_id = m.group(2), m.group(3)
        table_data = values.get(table_id)
        if not isinstance(table_data, list):
            return m.group(0)  # 非明细表:原样交给解析器按普通字段处理
        col_values = [float(row.get(col_id, 0) or 0) for row in table_data if isinstance(row, dict)]
        if not col_values:
            return "0"
        if agg == "sum":
            return str(sum(col_values))
        if agg == "avg":
            return str(sum(col_values) / len(col_values))
        if agg == "count":
            return str(len(col_values))
        if agg == "max":
            return str(max(col_values))
        if agg == "min":
            return str(min(col_values))
        return "0"

    def _countif_repl(m: re.Match) -> str:
        table_id, col_id, cond_str = m.group(1), m.group(2), m.group(3)
        table_data = values.get(table_id)
        if not isinstance(table_data, list):
            return "0"
        count = 0
        for row in table_data:
            if isinstance(row, dict):
                val = float(row.get(col_id, 0) or 0)
                if _eval_condition(val, cond_str):
                    count += 1
        return str(count)

    def _sumif_repl(m: re.Match) -> str:
        table_id, val_col = m.group(1), m.group(2)
        _, cond_col, cond_val = m.group(3), m.group(4), m.group(5)
        table_data = values.get(table_id)
        if not isinstance(table_data, list):
            return "0"
        total = 0.0
        for row in table_data:
            if isinstance(row, dict):
                if str(row.get(cond_col, "")) == cond_val:
                    total += float(row.get(val_col, 0) or 0)
        return str(total)

    def _textlocation_repl(m: re.Match) -> str:
        field_id, fmt = m.group(1), m.group(2)
        text = _text_location(values.get(field_id), fmt).replace('"', "")
        return f'"{text}"'

    def _distance_repl(m: re.Match) -> str:
        d = _distance_meters(values.get(m.group(1)), values.get(m.group(2)))
        return str(round(d, 2)) if d is not None else "0"

    def _textuser_repl(m: re.Match) -> str:
        s = _text_user(values.get(m.group(1)), m.group(2) or "name", values.get("__user_map__") or {})
        return '"' + s.replace('"', "") + '"'

    def _textdept_repl(m: re.Match) -> str:
        s = _text_dept(values.get(m.group(1)), m.group(2) or "name", values.get("__dept_map__") or {})
        return '"' + s.replace('"', "") + '"'

    def _textphone_repl(m: re.Match) -> str:
        raw = values.get(m.group(1))
        fmt = (m.group(2) or "phone").lower()
        if fmt == "verified":
            ok = isinstance(raw, dict) and bool(raw.get("verified"))
            return "1" if ok else "0"
        val = raw.get("phone") if isinstance(raw, dict) else raw
        return '"' + _to_str(val).replace('"', "") + '"'

    def _mapx_repl(m: re.Match) -> str:
        # 结果由异步构造器预算好放进 __mapx__(键=完整 MAPX 调用串);未预算(如前端预览)→ 0/空
        mapx = values.get("__mapx__") or {}
        return _to_str(mapx.get(m.group(0), "0"))

    result = _SUBTOTAL_RE.sub(_subtotal_repl, formula)
    result = _MULTI_AGG_RE.sub(_multi_agg_repl, result)
    result = _COUNTIF_RE.sub(_countif_repl, result)
    result = _SUMIF_RE.sub(_sumif_repl, result)
    result = _TEXTLOCATION_RE.sub(_textlocation_repl, result)
    result = _DISTANCE_RE.sub(_distance_repl, result)
    result = _TEXTUSER_RE.sub(_textuser_repl, result)
    result = _TEXTDEPT_RE.sub(_textdept_repl, result)
    result = _TEXTPHONE_RE.sub(_textphone_repl, result)
    result = _MAPX_RE.sub(_mapx_repl, result)
    return result


# ========== Public API ==========

def evaluate_formula(formula: str, values: dict[str, Any]) -> Any:
    """Evaluate formula and return result, or None on error."""
    result = evaluate_formula_with_error(formula, values)
    return None if result["error"] else result["value"]


def evaluate_formula_with_error(formula: str, values: dict[str, Any]) -> dict[str, Any]:
    """Evaluate formula, return {"value": ..., "error": ...}."""
    try:
        processed = _preprocess(formula, values)
        tokens = tokenize(processed)
        parser = Parser(tokens, values)
        value = parser.parse()
        return {"value": value, "error": None}
    except Exception as e:
        return {"value": None, "error": str(e)}


def evaluate_row_formula(
    formula: str,
    row_values: dict[str, Any],
    parent_values: dict[str, Any],
) -> Any:
    """Evaluate formula in detail table row context."""
    merged = {**parent_values, **row_values}
    return evaluate_formula(formula, merged)


def build_formula_context(
    form_data: dict[str, Any],
    field_definitions: list[dict[str, Any]],
    current_user_name: str = "",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造顶层公式求值上下文:表单数据 + 当前用户 + DB 依赖预算(extras),
    并把选项字段(单选/复选/下拉…)的存储值解析为标签(value→label),
    使公式里对选项「标签」的比较与显示一致(与 compute_formula_fields 完全同源)。"""
    context = {**form_data, "__currentUser__": current_user_name}
    if extras:
        context.update(extras)
    for field_def in field_definitions:
        options = field_def.get("options") or []
        if not options:
            continue
        opt_map = {o["value"]: o["label"] for o in options if "value" in o and "label" in o}
        if not opt_map:
            continue
        raw = context.get(field_def["id"])
        if isinstance(raw, list):
            context[field_def["id"]] = ", ".join(opt_map.get(v, str(v)) for v in raw)
        elif isinstance(raw, str) and raw in opt_map:
            context[field_def["id"]] = opt_map[raw]
    return context


def evaluate_submit_validations(
    form_data: dict[str, Any],
    field_definitions: list[dict[str, Any]],
    rules: list[dict[str, Any]],
    current_user_name: str = "",
    extras: dict[str, Any] | None = None,
) -> str | None:
    """表单提交校验(对齐简道云 doc/9039「表单提交校验」):逐条按公式求值,
    公式为真(满足条件)才允许提交;不满足则返回该条的提示文字拦截提交。

    - rules: [{formula, message}](formula 用 $字段id# 引用,与计算字段同源)。
    - 公式求值异常按「通过」处理,不误伤业务提交(与聚合表校验一致)。
    - 返回第一条不满足条件的提示文字;全部通过返回 None。
    """
    if not rules:
        return None
    context = build_formula_context(form_data, field_definitions, current_user_name, extras)
    for rule in rules:
        formula = (rule or {}).get("formula")
        if not formula or not isinstance(formula, str):
            continue
        res = evaluate_formula_with_error(formula, context)
        if res["error"]:
            continue
        if not _to_bool(res["value"]):
            return str((rule or {}).get("message") or "").strip() or "表单提交校验未通过"
    return None


def compute_formula_fields(
    form_data: dict[str, Any],
    field_definitions: list[dict[str, Any]],
    current_user_name: str = "",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Compute all formula field values and return updated form_data.
    Handles both top-level formula fields and detail table formula columns.

    extras: DB 依赖型函数的预算上下文(__user_map__/__dept_map__/__mapx__),
    由 services/formula_context.build_formula_extras 在写入路径预取注入。
    """
    result = dict(form_data)
    # 顶层求值上下文(表单数据 + 当前用户 + extras + 选项 value→label),与提交校验同源
    context = build_formula_context(result, field_definitions, current_user_name, extras)

    # Top-level formula fields
    for field_def in field_definitions:
        props = field_def.get("props") or {}
        formula = props.get("formula")
        if not formula or not isinstance(formula, str):
            continue
        if field_def.get("type") == "detail_table":
            continue
        # 「可编辑公式默认值」(formula_editable):公式仅作初值,提交时已有非空值则尊重用户改值,不复算覆盖
        if props.get("formula_editable"):
            existing = result.get(field_def["id"])
            if existing not in (None, "", []):
                context[field_def["id"]] = existing
                continue
        val = evaluate_formula(formula, context)
        if val is not None:
            result[field_def["id"]] = val
            context[field_def["id"]] = val

    # Detail table formula columns
    for field_def in field_definitions:
        if field_def.get("type") != "detail_table":
            continue
        columns = field_def.get("detail_table_columns") or []
        formula_cols = [
            c for c in columns
            if (c.get("props") or {}).get("formula") and isinstance((c.get("props") or {}).get("formula"), str)
        ]
        if not formula_cols:
            continue

        table_key = field_def["id"]
        rows = result.get(table_key)
        if not isinstance(rows, list):
            continue

        updated_rows = []
        for row_idx, row in enumerate(rows):
            if not isinstance(row, dict):
                updated_rows.append(row)
                continue
            updated_row = dict(row)
            # Resolve option columns: value → label
            row_with_labels = dict(updated_row)
            for col_def in columns:
                col_options = col_def.get("options") or []
                if not col_options:
                    continue
                col_opt_map = {o["value"]: o["label"] for o in col_options if "value" in o and "label" in o}
                col_raw = row_with_labels.get(col_def["id"])
                if isinstance(col_raw, list):
                    row_with_labels[col_def["id"]] = ", ".join(col_opt_map.get(v, str(v)) for v in col_raw)
                elif isinstance(col_raw, str) and col_raw in col_opt_map:
                    row_with_labels[col_def["id"]] = col_opt_map[col_raw]
            for col in formula_cols:
                row_context = {**context, **row_with_labels, "__rowIndex__": row_idx + 1}
                val = evaluate_formula(col["props"]["formula"], row_context)
                if val is not None:
                    updated_row[col["id"]] = val
            updated_rows.append(updated_row)
        result[table_key] = updated_rows

    return result
