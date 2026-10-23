"""Deterministic analysis over application data; no SQL or Python from users."""

import ast
import math
import operator
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

import config
from processing.analysis_models import Panel
from storage import app_db

FIELDS = {
    "title": ("作品名", "text"),
    "date": ("日付（JST）", "date"),
    "posted_at": ("投稿日時", "date"),
    "measured_at": ("計測日時", "date"),
    "character": ("キャラクター", "text"),
    "tags": ("タグ", "text"),
    "status": ("状態", "text"),
    "stage": ("計測ステージ", "text"),
    "elapsed_hours": ("投稿後の経過時間（h）", "number"),
    "elapsed_seconds": ("経過秒数", "number"),
    "likes": ("いいね", "number"),
    "retweets": ("リポスト", "number"),
    "impressions": ("インプレッション", "number"),
    "followers": ("フォロワー数", "number"),
    "new_fans_count": ("新規反応者", "number"),
}
FOLLOWER_FIELDS = {"date", "measured_at", "followers"}
FUNCTIONS = {
    "sum",
    "mean",
    "median",
    "min",
    "max",
    "count",
    "abs",
    "round",
    "sqrt",
    "log",
    "log10",
    "coalesce",
}
BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
}


class WeightedValues(list):
    def __init__(self, samples):
        samples = list(samples)
        super().__init__(value for value, _ in samples)
        self.weights = [weight for _, weight in samples]


def available_fields(source):
    return {
        key: value
        for key, value in FIELDS.items()
        if source != "followers" or key in FOLLOWER_FIELDS
    }


def parse_formula(expression, names):
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError) as error:
        raise ValueError("計算式の構文を確認してください") from error
    nodes = list(ast.walk(tree))
    if len(nodes) > 120:
        raise ValueError("計算式が複雑すぎます")
    allowed = (
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Call,
        ast.IfExp,
        ast.Compare,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.Not,
        ast.UAdd,
        ast.USub,
        *BIN_OPS,
        *CMP_OPS,
    )
    for node in nodes:
        if not isinstance(node, allowed):
            raise ValueError(  # noqa: TRY004 - unsupported syntax is a validation error
                "計算式には数値・列名・許可された関数と演算だけを使用できます"
            )
        if isinstance(node, ast.Name) and node.id not in names | FUNCTIONS:
            raise ValueError(f"不明な列または関数: {node.id}")
        if isinstance(node, ast.Constant) and (
            type(node.value) not in (int, float, bool) or abs(node.value) > 1e12
        ):
            raise ValueError("計算式の定数は有限の数値にしてください")
        if isinstance(node, ast.Call) and (
            not isinstance(node.func, ast.Name)
            or node.func.id not in FUNCTIONS
            or node.keywords
            or not 1 <= len(node.args) <= 6
        ):
            raise ValueError("許可された関数と引数を使用してください")
    return tree.body


def evaluate(node, values):
    """Missing operands and arithmetic domain errors yield a missing result."""

    def visit(item):
        if isinstance(item, ast.Constant):
            return item.value
        if isinstance(item, ast.Name):
            return values.get(item.id)
        if isinstance(item, ast.BinOp):
            left, right = visit(item.left), visit(item.right)
            if left is None or right is None:
                return None
            if isinstance(item.op, ast.Pow) and abs(right) > 12:
                return None
            return BIN_OPS[type(item.op)](left, right)
        if isinstance(item, ast.UnaryOp):
            value = visit(item.operand)
            if value is None:
                return None
            return (
                not value
                if isinstance(item.op, ast.Not)
                else (-value if isinstance(item.op, ast.USub) else value)
            )
        if isinstance(item, ast.IfExp):
            return visit(item.body) if visit(item.test) else visit(item.orelse)
        if isinstance(item, ast.Compare):
            left = visit(item.left)
            for op, other in zip(item.ops, item.comparators):
                right = visit(other)
                if left is None or right is None or not CMP_OPS[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(item, ast.BoolOp):
            results = [bool(visit(value)) for value in item.values]
            return all(results) if isinstance(item.op, ast.And) else any(results)
        if isinstance(item, ast.Call):
            name = item.func.id
            args = [visit(arg) for arg in item.args]
            if name == "coalesce":
                return next((arg for arg in args if arg is not None), None)
            if name in {"sum", "mean", "median", "min", "max", "count"}:
                samples = []
                for arg in args:
                    pairs = (
                        zip(arg, arg.weights)
                        if isinstance(arg, WeightedValues)
                        else (
                            (value, 1)
                            for value in (arg if isinstance(arg, list) else [arg])
                        )
                    )
                    samples.extend(
                        (value, weight)
                        for value, weight in pairs
                        if isinstance(value, (int, float)) and math.isfinite(value)
                    )
                if name == "count":
                    return sum(weight for _, weight in samples)
                if not samples:
                    return None
                return aggregate(samples, name)
            if any(arg is None for arg in args):
                return None
            return {
                "abs": abs,
                "round": round,
                "sqrt": math.sqrt,
                "log": math.log,
                "log10": math.log10,
            }[name](*args)
        raise ValueError("計算式を評価できません")

    try:
        result = visit(node)
        return (
            result
            if isinstance(result, (int, float))
            and math.isfinite(result)
            and abs(result) <= 1e100
            else None
        )
    except (ArithmeticError, ValueError, TypeError, OverflowError):
        return None


def validate_panel(panel: Panel):
    fields = available_fields(panel.source)
    if panel.stage not in config.STAGE_MAP:
        raise ValueError("計測ステージを選択してください")
    row_names = {key for key, (_, kind) in fields.items() if kind == "number"}
    all_names = set(fields)
    trees = {}
    for formula in panel.formulas:
        if formula.key in all_names:
            raise ValueError("計算列のキーが重複しています")
        trees[formula.key] = parse_formula(formula.expression, row_names)
        all_names.add(formula.key)
        if formula.scope == "row":
            row_names.add(formula.key)
    group_names = {f.key for f in panel.formulas if f.scope == "group"}
    if panel.x not in all_names - group_names or (
        panel.series and panel.series not in all_names - group_names
    ):
        raise ValueError("このデータ種類で使用できる横軸・系列を選択してください")
    if any(key not in row_names | group_names for key in panel.y):
        raise ValueError("縦軸には数値列または計算列を選択してください")
    if panel.chart in {"box", "histogram"} and any(
        key in group_names for key in panel.y
    ):
        raise ValueError(
            "分布には行ごとの数値を使用してください。集計後の計算式は使用できません"
        )
    if panel.chart == "table" and any(
        key not in all_names - group_names for key in panel.columns
    ):
        raise ValueError("テーブルに表示する列を確認してください")
    if panel.chart == "table" and not panel.columns:
        raise ValueError("テーブルには1つ以上の表示列を選択してください")
    if panel.chart == "table":
        table_fields = all_names - group_names
        if panel.table_group and panel.table_group not in table_fields:
            raise ValueError("このデータで使用できるグループ化項目を選択してください")
        sort_fields = (
            [sort.field for sort in panel.table_sorts]
            if panel.table_sorts is not None
            else [panel.table_sort]
        )
        if any(field not in table_fields for field in sort_fields):
            raise ValueError("このデータで使用できる並べ替え項目を選択してください")
        if len(set(sort_fields)) != len(sort_fields):
            raise ValueError("並べ替え項目が重複しています")
    if panel.chart == "pie" and len(panel.y) != 1:
        raise ValueError("円グラフの数値は1つ選択してください")
    if panel.transform != "none" and panel.chart != "line":
        raise ValueError("集計後の増加・移動平均は折れ線グラフで使用できます")
    for group in panel.filters:
        for rule in group.rules:
            if rule.field not in all_names - group_names and rule.field != "characters":
                raise ValueError(f"不明なフィルター項目: {rule.field}")
    for value in [panel.from_date, panel.to_date]:
        if value:
            date.fromisoformat(value)
    if panel.from_date and panel.to_date and panel.from_date > panel.to_date:
        raise ValueError("開始日は終了日以前にしてください")
    if panel.compare_previous and not (
        panel.period_days or (panel.from_date and panel.to_date)
    ):
        raise ValueError(
            "前期間比較では直近の日数、または開始日と終了日を指定してください"
        )
    if panel.compare_previous and panel.chart in {"table", "pie"}:
        raise ValueError("前期間比較は折れ線・箱ひげ図・ヒストグラムで使用できます")
    return trees


def match_rule(row, rule):
    value = row.get(rule.field)
    if rule.op == "empty":
        return value is None or value == "" or value == [] or value == "未設定"
    if rule.op == "contains":
        return (
            str(rule.value).casefold() in str(value).casefold()
            if value is not None
            else False
        )
    if rule.op in {"eq", "ne"}:
        if isinstance(value, (int, float)):
            try:
                equal = value == float(rule.value)
            except (TypeError, ValueError):
                equal = False
        else:
            equal = (
                str(rule.value) in [str(v) for v in value]
                if isinstance(value, list)
                else value == rule.value
            )
        return equal if rule.op == "eq" else not equal
    try:
        return {
            "gt": operator.gt,
            "gte": operator.ge,
            "lt": operator.lt,
            "lte": operator.le,
        }[rule.op](float(value), float(rule.value))
    except (TypeError, ValueError):
        return False


def matches(row, panel):
    groups = []
    for group in panel.filters:
        if group.rules:
            results = [match_rule(row, rule) for rule in group.rules]
            groups.append(all(results) if group.join == "and" else any(results))
    return (
        (all(groups) if panel.filter_join == "and" else any(groups)) if groups else True
    )


def weighted_quantile(samples, proportion):
    samples = sorted(samples)
    if not samples:
        return None
    # Linear interpolation is used for unweighted distributions (standard Q1/Q3).
    if len({weight for _, weight in samples}) == 1:
        position = (len(samples) - 1) * proportion
        lower, upper = math.floor(position), math.ceil(position)
        return samples[lower][0] + (samples[upper][0] - samples[lower][0]) * (
            position - lower
        )
    target = sum(weight for _, weight in samples) * proportion
    cumulative = 0
    for value, weight in samples:
        cumulative += weight
        if cumulative >= target:
            return value
    return samples[-1][0]


def aggregate(samples, method):
    if not samples:
        return None
    if method == "count":
        return sum(weight for _, weight in samples)
    if method == "sum":
        return sum(value * weight for value, weight in samples)
    if method == "mean":
        return sum(value * weight for value, weight in samples) / sum(
            weight for _, weight in samples
        )
    if method == "median":
        return weighted_quantile(samples, 0.5)
    return (
        min(value for value, _ in samples)
        if method == "min"
        else max(value for value, _ in samples)
    )


def query(panel: Panel, *, now=None, rows=None):
    trees = validate_panel(panel)
    today = now or datetime.now(app_db.JST).date()
    end = date.fromisoformat(panel.to_date) if panel.to_date else today
    start = (
        date.fromisoformat(panel.from_date)
        if panel.from_date
        else (
            end - timedelta(days=panel.period_days - 1)
            if panel.period_days
            else date.min
        )
    )
    days = (end - start).days + 1
    try:
        previous_start = (
            start - timedelta(days=days) if panel.compare_previous else start
        )
    except OverflowError as error:
        raise ValueError("比較する期間を短くしてください") from error
    rows = (
        app_db.analysis_rows(
            panel.source,
            panel.stage,
            from_date=previous_start.isoformat(),
            to_date=end.isoformat(),
        )
        if rows is None
        else [dict(row) for row in rows]
    )
    selected = []
    for row in rows:
        if not previous_start.isoformat() <= row["date"] <= end.isoformat():
            continue
        for formula in panel.formulas:
            if formula.scope == "row":
                row[formula.key] = evaluate(trees[formula.key], row)
        if not matches(row, panel):
            continue
        row["period"] = "前期間" if row["date"] < start.isoformat() else "現在"
        selected.append(row)
    missing = {
        row["artwork_id"]
        for row in selected
        if panel.source == "artworks" and not row.get("snapshot_id")
    }
    output = {
        "input_count": len(selected),
        "artwork_count": len(
            {row.get("artwork_id", row["row_id"]) for row in selected}
        ),
        "missing_stage_count": len(missing),
        "excluded_count": 0,
        "points": [],
        "rows": [],
        "warnings": [],
        "fields": {
            key: value[0] for key, value in available_fields(panel.source).items()
        }
        | {f.key: f.label for f in panel.formulas},
    }
    if panel.chart == "table":
        output["rows"] = selected
        output["excluded_count"] = len(missing)
        return output
    needs_char = panel.x == "character" or panel.series == "character"
    buckets = defaultdict(list)
    missing_metric = set()
    for row in selected:
        if panel.source == "artworks" and not row.get("snapshot_id"):
            continue
        characters = row.get("characters") or ["未設定"]
        expand = (
            characters
            if needs_char and panel.allocation != "combination"
            else [" + ".join(characters)]
        )
        weight = (
            1 / len(characters) if needs_char and panel.allocation == "split" else 1
        )
        for character in expand:
            expanded = row | {"character": character}
            x = expanded.get(panel.x)
            if x is None:
                missing_metric.add(row["row_id"])
                continue
            if isinstance(x, list):
                x = ", ".join(x)
            # Previous calendar series are aligned to the current period's dates.
            if (
                panel.compare_previous
                and row["period"] == "前期間"
                and panel.x == "date"
            ):
                x = (date.fromisoformat(x) + timedelta(days=days)).isoformat()
            series = expanded.get(panel.series, "") if panel.series else ""
            if isinstance(series, list):
                series = ", ".join(series)
            for y in panel.y:
                label = " / ".join(
                    str(part)
                    for part in [
                        series,
                        output["fields"][y] if len(panel.y) > 1 else "",
                        row["period"] if panel.compare_previous else "",
                    ]
                    if part
                )
                buckets[(x, label, y)].append((expanded, weight))
    group_keys = {f.key for f in panel.formulas if f.scope == "group"}
    for (x, series, y), items in buckets.items():
        if y in group_keys:
            # Fractional allocation applies to contributions of every aggregate operand.
            values = {
                key: WeightedValues(
                    (row.get(key), weight)
                    for row, weight in items
                    if isinstance(row.get(key), (int, float))
                )
                for key in set(FIELDS) | set(trees)
            }
            value = evaluate(trees[y], values)
            samples = []
        else:
            samples = [
                (row[y], weight)
                for row, weight in items
                if isinstance(row.get(y), (int, float)) and math.isfinite(row[y])
            ]
            for row, _ in items:
                if row.get(y) is None:
                    missing_metric.add(row["row_id"])
            value = aggregate(samples, panel.aggregate)
        if value is not None:
            output["points"].append(
                {
                    "x": x,
                    "series": series,
                    "metric": y,
                    "y": value,
                    "n": len(items) if y in group_keys else len(samples),
                    "samples": samples,
                }
            )
        else:
            missing_metric.update(row["row_id"] for row, _ in items)
    output["excluded_count"] = len(missing) + len(missing_metric)
    # Numerical axes retain actual coordinates; date axes are ISO chronological strings.
    output["points"].sort(
        key=lambda point: (
            str(point["series"]),
            float(point["x"])
            if isinstance(point["x"], (int, float))
            else str(point["x"]),
        )
    )
    if panel.transform != "none":
        grouped = defaultdict(list)
        for point in output["points"]:
            grouped[(point["series"], point["metric"])].append(point)
        for series in grouped.values():
            original = [point["y"] for point in series]
            for index, point in enumerate(series):
                prior = original[index - 1] if index else None
                if panel.transform == "moving_average":
                    point["y"] = statistics.mean(
                        original[max(0, index - panel.window + 1) : index + 1]
                    )
                elif prior is None or (panel.transform == "rate" and prior == 0):
                    point["y"] = None
                else:
                    point["y"] = (
                        original[index] - prior
                        if panel.transform == "delta"
                        else (original[index] - prior) / abs(prior) * 100
                    )
    if panel.chart == "box":
        for point in output["points"]:
            samples = point.pop("samples")
            q1, med, q3 = [weighted_quantile(samples, q) for q in [0.25, 0.5, 0.75]]
            low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
            inside = [value for value, _ in samples if low <= value <= high]
            point.update(
                q1=q1,
                median=med,
                q3=q3,
                low=min(inside),
                high=max(inside),
                outliers=[value for value, _ in samples if value < low or value > high],
            )
    elif panel.chart == "histogram":
        grouped = defaultdict(list)
        for point in output["points"]:
            grouped[(point["series"], point["metric"])].extend(point["samples"])
        all_values = [v for samples in grouped.values() for v, _ in samples]
        points = []
        if all_values:
            low, high = min(all_values), max(all_values)
            width = (high - low) / panel.bins if high > low else 1
            for (series, metric), samples in grouped.items():
                counts = [0.0] * panel.bins
                for value, weight in samples:
                    counts[min(panel.bins - 1, int((value - low) / width))] += weight
                points.extend(
                    {
                        "x": low + (i + 0.5) * width,
                        "start": low + i * width,
                        "end": low + (i + 1) * width,
                        "y": count,
                        "series": series,
                        "metric": metric,
                    }
                    for i, count in enumerate(counts)
                )
        output["points"] = points
    else:
        for point in output["points"]:
            point.pop("samples", None)
    if panel.chart == "pie" and any(
        point["y"] is not None and point["y"] < 0 for point in output["points"]
    ):
        raise ValueError("円グラフには負の値を使用できません")
    sort = panel.style.sort
    if sort in {"y_asc", "y_desc"}:
        output["points"].sort(
            key=lambda p: p["y"] if p["y"] is not None else -math.inf,
            reverse=sort == "y_desc",
        )
    elif sort == "x_desc":
        output["points"].reverse()
    if needs_char and panel.allocation == "full":
        output["warnings"].append(
            "複数キャラ作品は各キャラに全量計上しています。キャラ別合計には重複を含みます。"
        )
    if panel.allocation == "split" and needs_char:
        output["warnings"].append(
            "均等配分：件数・合計は1÷キャラ数で配分。平均・分位数は同じ重みによる加重統計です。"
        )
    if panel.transform != "none":
        output["warnings"].append(
            "増加・移動平均は、系列内で横軸を昇順に並べた集計点に対して計算します。単位は観測点です。"
        )
    if len(output["points"]) > 2500:
        raise ValueError(
            "グラフは2,500点までです。フィルターや集計で点数を減らしてください"
        )
    return output
