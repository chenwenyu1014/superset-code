"""
ODPS `default` schema 修复 —— 离线验证脚本（不依赖 superset 包）

复刻改动涉及的逻辑，用 SQLAlchemy 的 MySQL 方言构造一个离线
identifier_preparer，在本机即可验证修复行为。只依赖 sqlalchemy。

    pip install sqlalchemy   # 如已装可跳过
    python verify_offline.py

期望末行 ALL PASS。
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import table, column, select
from sqlalchemy.dialects import mysql


# --------------------------------------------------------------------------- #
# 复刻 superset/sql/parse.py 的 Table（只取需要的三个字段）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Table:
    table: str
    schema: str | None = None
    catalog: str | None = None


# --------------------------------------------------------------------------- #
# 复刻 BaseEngineSpec.quote_table（改动前基类原样）
# --------------------------------------------------------------------------- #
def base_quote_table(table_obj: Table, dialect) -> str:
    quoters = {
        "catalog": dialect.identifier_preparer.quote_schema,
        "schema": dialect.identifier_preparer.quote_schema,
        "table": dialect.identifier_preparer.quote,
    }
    return ".".join(
        fn(getattr(table_obj, key))
        for key, fn in quoters.items()
        if getattr(table_obj, key)
    )


# --------------------------------------------------------------------------- #
# 复刻改动后的 OdpsBaseEngineSpec 三段覆盖
# --------------------------------------------------------------------------- #
PLACEHOLDER_SCHEMA = "default"


def odps_normalize_schema(schema: str | None) -> str | None:
    return None if schema == PLACEHOLDER_SCHEMA else schema


def odps_get_default_schema() -> str | None:
    # 覆盖实现：直接返回 None，不依赖 database 参数
    return None


def odps_quote_table(table_obj: Table, dialect) -> str:
    if table_obj.schema == PLACEHOLDER_SCHEMA:
        table_obj = Table(table=table_obj.table, schema=None, catalog=table_obj.catalog)
    return base_quote_table(table_obj, dialect)


# --------------------------------------------------------------------------- #
# 复刻改动后的 SqlaTable.get_sqla_table（非 cross-catalog 分支）
#   schema = db_engine_spec.normalize_schema(self.schema)
#   if schema:  return table(name, schema=schema)
#   return table(name)
# 用 compile() 看实际下发 SQL 的 FROM 片段。
# --------------------------------------------------------------------------- #
def chart_from_clause(table_name: str, schema: str | None, dialect) -> str:
    # TableClause 单独 compile 不渲染 FROM，必须放进 SELECT 才能看到 FROM 子句
    # （这也是 chart 查询里该 TableClause 的实际用法）。
    schema = odps_normalize_schema(schema)
    if schema:
        t = table(table_name, schema=schema)
    else:
        t = table(table_name)
    return str(select(column("c")).select_from(t).compile(dialect=dialect))


def main() -> None:
    dialect = mysql.dialect()
    ok = True

    print("== normalize_schema ==")
    for inp, exp in [("default", None), ("my_schema", "my_schema"), (None, None)]:
        got = odps_normalize_schema(inp)
        flag = "OK" if got == exp else "FAIL"
        ok &= got == exp
        print(f"  [{flag}] normalize_schema({inp!r}) -> {got!r}  (期望 {exp!r})")

    print("== get_default_schema ==")
    got = odps_get_default_schema()
    ok &= got is None
    print(f"  [{'OK' if got is None else 'FAIL'}] get_default_schema() -> {got!r}  (期望 None)")

    print("== quote_table (表预览 select_star 路径) ==")
    out = odps_quote_table(Table("v_monitoringoverduelist", "default"), dialect)
    cond = "default" not in out.lower()
    ok &= cond
    print(f"  [{'OK' if cond else 'FAIL'}] schema='default' -> {out!r}  (期望无 'default.' 前缀)")

    out = odps_quote_table(Table("t", "my_schema"), dialect)
    cond = "my_schema" in out
    ok &= cond
    print(f"  [{'OK' if cond else 'FAIL'}] schema='my_schema' -> {out!r}  (期望含 'my_schema')")

    print("== chart/dataset FROM 子句 (get_sqla_table 路径) ==")
    out = chart_from_clause("v_monitoringoverduelist", "default", dialect)
    cond = "default" not in out.lower() and "v_monitoringoverduelist" in out
    ok &= cond
    print(f"  [{'OK' if cond else 'FAIL'}] schema='default' -> {out!r}  (期望无 'default.' 前缀)")

    out = chart_from_clause("t", "my_schema", dialect)
    cond = "my_schema" in out
    ok &= cond
    print(f"  [{'OK' if cond else 'FAIL'}] schema='my_schema' -> {out!r}  (期望含 'my_schema')")

    print()
    print("ALL PASS" if ok else "FAIL —— 逻辑与预期不符，请检查")


if __name__ == "__main__":
    main()