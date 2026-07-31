"""
ODPS `default` schema 修复验证脚本。
在部署环境（能正常 import superset 的环境）运行：

    python verify_fix.py

期望全部 PASS。失败则说明改动未生效或被覆盖。
"""
from __future__ import annotations

from superset.db_engine_specs.odps import OdpsBaseEngineSpec
from superset.sql.parse import Table

def _get_dialect():
    # 用 MySQL 方言构造一个离线 identifier_preparer（不需要真实连接）
    from sqlalchemy.dialects import mysql

    return mysql.dialect()


def main() -> None:
    spec = OdpsBaseEngineSpec
    ok = True

    # 1) normalize_schema
    got = spec.normalize_schema("default")
    print(f"normalize_schema('default') -> {got!r}  (期望 None)")
    ok &= got is None

    got = spec.normalize_schema("my_schema")
    print(f"normalize_schema('my_schema') -> {got!r}  (期望 'my_schema')")
    ok &= got == "my_schema"

    got = spec.normalize_schema(None)
    print(f"normalize_schema(None) -> {got!r}  (期望 None)")
    ok &= got is None

    # 2) get_default_schema：覆盖实现应直接返回 None，不依赖 database 参数
    got = spec.get_default_schema(database=None, catalog=None)  # type: ignore[arg-type]
    print(f"get_default_schema(...) -> {got!r}  (期望 None)")
    ok &= got is None

    # 3) quote_table：schema=default 时不应出现 default. 前缀
    dialect = _get_dialect()
    out = spec.quote_table(Table(table="v_monitoringoverduelist", schema="default"), dialect)
    print(f"quote_table(schema='default') -> {out!r}  (期望不含 'default.' 前缀)")
    ok &= "default" not in out.lower() and "v_monitoringoverduelist" in out

    # 4) quote_table：真实 schema 应保留
    out = spec.quote_table(Table(table="t", schema="my_schema"), dialect)
    print(f"quote_table(schema='my_schema') -> {out!r}  (期望含 'my_schema')")
    ok &= "my_schema" in out

    print()
    print("ALL PASS" if ok else "FAIL —— 请检查改动是否已部署生效")


if __name__ == "__main__":
    main()
