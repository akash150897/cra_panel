"""Validates the structure of rule definition dictionaries."""

from typing import Any, Dict, List, Tuple

_REQUIRED_FIELDS = ("id", "name", "severity", "type", "message")
_VALID_SEVERITIES = {"error", "warning", "info"}
_VALID_TYPES = {"regex", "ast", "filename"}


def validate_rule(rule: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a single rule dictionary.

    Args:
        rule: Rule dictionary to validate.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors: List[str] = []
    rule_id = rule.get("id", "<unknown>")

    for field in _REQUIRED_FIELDS:
        if field not in rule:
            errors.append(f"Rule '{rule_id}': missing required field '{field}'")

    severity = rule.get("severity", "").lower()
    if severity and severity not in _VALID_SEVERITIES:
        errors.append(
            f"Rule '{rule_id}': invalid severity '{severity}'. "
            f"Must be one of {sorted(_VALID_SEVERITIES)}"
        )

    rule_type = rule.get("type", "").lower()
    if rule_type and rule_type not in _VALID_TYPES:
        errors.append(
            f"Rule '{rule_id}': invalid type '{rule_type}'. "
            f"Must be one of {sorted(_VALID_TYPES)}"
        )

    if rule_type == "regex" and not rule.get("pattern"):
        errors.append(f"Rule '{rule_id}': regex rules require a 'pattern' field")

    if rule_type == "ast" and not rule.get("ast_check"):
        errors.append(f"Rule '{rule_id}': ast rules require an 'ast_check' field")

    return len(errors) == 0, errors


def validate_rule_file(data: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Validate a complete rule file (top-level dict with a 'rules' list).

    Args:
        data: Parsed JSON content of a rule file.

    Returns:
        (is_valid, list_of_error_messages)
    """
    all_errors: List[str] = []

    if "rules" not in data:
        all_errors.append("Rule file missing top-level 'rules' key")
        return False, all_errors

    if not isinstance(data["rules"], list):
        all_errors.append("Top-level 'rules' must be a list")
        return False, all_errors

    seen_ids: set = set()
    for rule in data["rules"]:
        if not isinstance(rule, dict):
            all_errors.append("Each rule must be a JSON object")
            continue
        rule_id = rule.get("id", "")
        if rule_id in seen_ids:
            all_errors.append(f"Duplicate rule id: '{rule_id}'")
        seen_ids.add(rule_id)
        _, errs = validate_rule(rule)
        all_errors.extend(errs)

    return len(all_errors) == 0, all_errors
