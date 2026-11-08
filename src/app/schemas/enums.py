from enum import StrEnum


class DataType(StrEnum):
    REAL = "real"
    INT = "int"
    STRING = "string"
    BOOL = "bool"


class NodeType(StrEnum):
    COMPARISON = "COMPARISON"
    LOGICAL = "LOGICAL"


class ComparisonOperator(StrEnum):
    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "IN"


class LogicalOperator(StrEnum):
    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class PolicyAction(StrEnum):
    INTERCEPT = "INTERCEPT"
    ALLOW_OVERRIDE = "ALLOW_OVERRIDE"
    STEP_UP_AUTH = "STEP_UP_AUTH"


class UpdateRequestStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED_MERGED = "APPROVED_MERGED"
    REJECTED = "REJECTED"


class RedTeamSource(StrEnum):
    Z3_RED_TEAM_SYNTH = "Z3_RED_TEAM_SYNTH"
    LIVE_ANOMALY_ESCAPEE = "LIVE_ANOMALY_ESCAPEE"


class VariableRole(StrEnum):
    INPUT = "INPUT"
    INTERMEDIATE = "INTERMEDIATE"
    OUTPUT = "OUTPUT"
    PARAMETER = "PARAMETER"


class VariableSort(StrEnum):
    REAL = "real"
    INT = "int"
    BOOL = "bool"


class ConceptModality(StrEnum):
    NUMERICAL = "numerical"
    ORDINAL = "ordinal"
    CATEGORICAL = "categorical"


class ConstraintOperator(StrEnum):
    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="


class AbductiveSolveStatus(StrEnum):
    SATISFIABLE = "SATISFIABLE"
    UNSATISFIABLE = "UNSATISFIABLE"


class CounterfactualStatus(StrEnum):
    COUNTERFACTUAL_FOUND = "COUNTERFACTUAL_FOUND"
    UNSAT = "UNSAT"


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    DEAD_LOGIC_DETECTED = "DEAD_LOGIC_DETECTED"


class DeadLogicClassification(StrEnum):
    PARAMETER_MISCALIBRATION = "PARAMETER_MISCALIBRATION"
    WRONG_RULE_COMPILER = "WRONG_RULE_COMPILER"
    WRONG_POLICY_MANDATE = "WRONG_POLICY_MANDATE"
