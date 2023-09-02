from enum import Enum


class CellFormat(Enum):
    NUMBER_WITH_SPACE = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0;#,##0;0"}}
    NUMBER_PERCENT = {"numberFormat": {"type": "NUMBER", "pattern": "0%"}}
