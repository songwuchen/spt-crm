"""扩展平台枚举常量。

移植自 spt-lowcode app/core/constants.py,保持字段类型/流程节点/审批人类型与原平台一致,
使前端设计器产出的 JSON 定义可被后端直接解释。
"""
from enum import StrEnum


# ===== 表单模板状态 =====

class FormTemplateStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


# ===== 表单实例状态 =====

class FormInstanceStatus(StrEnum):
    DRAFT = "draft"            # 草稿(暂存,未提交流程)
    SUBMITTED = "submitted"    # 已提交(无流程或流程外)
    RUNNING = "running"        # 审批流转中
    COMPLETED = "completed"    # 审批通过
    REJECTED = "rejected"      # 审批驳回
    WITHDRAWN = "withdrawn"    # 已撤回


# ===== 字段类型 =====

class FieldType(StrEnum):
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    AMOUNT = "amount"
    DATE = "date"
    DATETIME = "datetime"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    PERSON = "person"
    PERSON_MULTI = "person_multi"
    DEPARTMENT = "department"
    DEPARTMENT_MULTI = "department_multi"
    FILE = "file"
    IMAGE = "image"
    DETAIL_TABLE = "detail_table"       # 明细子表
    FORMULA = "formula"
    AUTO_NUMBER = "auto_number"          # 流水号
    RELATED_DOC = "related_doc"
    ADDRESS = "address"
    LOCATION = "location"
    SWITCH = "switch"
    CASCADE = "cascade"
    RICH_TEXT = "rich_text"
    SIGNATURE = "signature"
    SELECT_DATA = "select_data"          # 从另一表单取数
    RELATION = "relation"
    SUB_TABLE_DATA = "sub_table_data"    # 关联子表(主表内联操作另一独立表单的多条记录)


#: 可作为明细子表列的字段类型白名单(与前端 detailColumnTypes 对齐)
DETAIL_COLUMN_TYPES = {
    FieldType.TEXT, FieldType.TEXTAREA, FieldType.NUMBER, FieldType.AMOUNT,
    FieldType.DATE, FieldType.DATETIME, FieldType.SELECT, FieldType.MULTI_SELECT,
    FieldType.RADIO, FieldType.CHECKBOX, FieldType.PERSON, FieldType.DEPARTMENT,
    FieldType.FILE, FieldType.IMAGE, FieldType.FORMULA, FieldType.SWITCH,
}

#: 语义分组(供聚合/审批人解析使用)
PERSON_FIELD_TYPES = {FieldType.PERSON, FieldType.PERSON_MULTI}
DEPT_FIELD_TYPES = {FieldType.DEPARTMENT, FieldType.DEPARTMENT_MULTI}
DATE_FIELD_TYPES = {FieldType.DATE, FieldType.DATETIME}
NUMERIC_FIELD_TYPES = {FieldType.NUMBER, FieldType.AMOUNT, FieldType.FORMULA}


# ===== 流程定义 / 实例状态(Phase 3 使用) =====

class ProcessDefinitionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class ProcessInstanceStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    TERMINATED = "terminated"


class NodeInstanceStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class TaskInstanceStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TRANSFERRED = "transferred"
    WITHDRAWN = "withdrawn"
    CANCELLED = "cancelled"


class ActionType(StrEnum):
    SUBMIT = "submit"
    APPROVE = "approve"
    REJECT = "reject"
    WITHDRAW = "withdraw"
    TRANSFER = "transfer"
    ADD_SIGN = "add_sign"
    VETO = "veto"
    URGE = "urge"
    COMMENT = "comment"
    AUTO_APPROVE = "auto_approve"
    AUTO_REJECT = "auto_reject"
    AUTO_TRANSFER = "auto_transfer"
    TIMEOUT = "timeout"
    STASH = "stash"
    END_PROCESS = "end_process"
    ACTIVATE = "activate"
    ADJUST_ASSIGNEE = "adjust_assignee"


class NodeType(StrEnum):
    START = "start"
    APPROVAL = "approval"
    CC = "cc"
    CONDITION = "condition"
    PARALLEL = "parallel"
    MERGE = "merge"
    WEBHOOK = "webhook"
    SUB_PROCESS = "sub_process"
    PLUGIN = "plugin"
    END = "end"


class ApproverType(StrEnum):
    SPECIFIED_USER = "specified_user"
    DIRECT_SUPERVISOR = "direct_supervisor"
    DEPT_HEAD = "dept_head"
    MULTI_LEVEL_SUPERIOR = "multi_level_superior"
    SPECIFIED_ROLE = "specified_role"
    SPECIFIED_POST = "specified_post"
    FORM_FIELD_PERSON = "form_field_person"
    FORM_FIELD_DEPT = "form_field_dept"
    DEPT_MEMBERS = "dept_members"
    CREATOR = "creator"
    MIXED = "mixed"
    INITIATOR_SELF_SELECT = "initiator_self_select"


class MultiApprovalMode(StrEnum):
    SEQUENTIAL = "sequential"
    COUNTERSIGN = "countersign"   # 会签(全部通过)
    OR_SIGN = "or_sign"           # 或签(一人通过即可)


class FieldPermissionType(StrEnum):
    EDITABLE = "editable"
    READONLY = "readonly"
    HIDDEN = "hidden"
    REQUIRED = "required"


class ConditionOperator(StrEnum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
