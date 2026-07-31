"""
ODPS `default` schema 限定符 —— 配置级兜底修复

把下面 SQL_QUERY_MUTATOR 整段追加/替换到你【实际加载的】 superset_config.py
（不是仓库里的 superset/config.py，而是你的部署配置文件，通常通过
 SUPERSET_CONFIG_PATH 指定）。

原理：SQL_QUERY_MUTATOR 是 Superset 在【最终下发 SQL 前】的统一改写钩子，
覆盖所有查询路径（物理表 chart / 虚拟数据集 / SQL Lab），kwargs 里带 database，
可按引擎定向处理。对 ODPS，去掉占位 schema 限定符 default.，让裸表名按连接默认
project 解析，规避 ODPS-0130131。
"""
import re

# 匹配 "default".  或  `default`.  （两侧引号可为双引号或反引号，允许点前有空格）
_ODPS_DEFAULT_SCHEMA_QUALIFIER = re.compile(r'["`]default["`]\s*\.')


def SQL_QUERY_MUTATOR(sql: str, **kwargs) -> str:  # noqa: N802
    database = kwargs.get("database")
    spec = getattr(database, "db_engine_spec", None)
    if spec is not None and getattr(spec, "engine", None) == "odps":
        # 经典两层 MaxCompute 项目没有 default schema；元数据上报的 default
        # 占位限定符会让 ODPS 报 ODPS-0130131。去掉它，表名按默认 project 解析。
        sql = _ODPS_DEFAULT_SCHEMA_QUALIFIER.sub("", sql)
    return sql


# 若你的 SQL 里 default 是【不带引号】裸写（如 FROM default.table），取消下面注释，
# 它只在 FROM/JOIN 之后剥离 default. 前缀，降低误伤列别名/表别名的风险。
#
# _ODPS_DEFAULT_SCHEMA_QUALIFIER_UNQUOTED = re.compile(
#     r'(?i)(\bfrom\b|\bjoin\b)\s+default\s*\.',
# )
# 然后在上面 if 分支里追加：
#     sql = _ODPS_DEFAULT_SCHEMA_QUALIFIER_UNQUOTED.sub(lambda m: m.group(1) + " ", sql)