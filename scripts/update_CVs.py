"""Apply a CV or MIP table addition described by a GitHub issue form."""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "tables"
CV_PATH = TABLES / "UKCI_CV.json"
VARIABLES_TXT = ROOT / "cdds_ukci" / "variables.txt"
IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")
STREAM = re.compile(r"^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)?$")


class IssueError(Exception):
    """
    An error related to processing a GitHub issue form.
    """
    pass


def parse_issue_body(body):
    """
    Parse the body of a GitHub issue form into a dictionary of fields.
    """
    sections = {}
    current = None
    # Go through each line of the issue body
    for line in body.replace("\r\n", "\n").split("\n"):
        # Looks for a level 3 markdown heading (e.g., ### experiment_id)
        # (.+?) captures the heading text after "### " and ignores spaces
        heading = re.match(r"^###\s+(.+?)\s*$", line)
        # Puts the lines following the heading into the corresponding section
        if heading:
            current = heading.group(1)
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    fields = {}
    for key, lines in sections.items():
        value = "\n".join(lines).strip()
        # Convert "_No response_" to an empty string
        fields[key] = "" if value == "_No response_" else value
    return fields


def require(fields, key):
    """
    A utility function to ensure that a field is present and not empty in the issue form.
    """
    value = fields.get(key, "").strip()
    if not value:
        raise IssueError(f"Missing required field '{key}'.")
    return value


def require_identifier(fields, key):
    """
    A utility function to ensure that a field is present, not empty, and matches the identifier pattern.
    """
    value = require(fields, key)
    if not IDENTIFIER.match(value):
        raise IssueError(f"'{key}' must match {IDENTIFIER.pattern}, got '{value}'.")
    return value


def split_list(value):
    """
    A utility function to split a comma-separated list into individual items, stripping whitespace and ignoring empty items.
    """
    return [item.strip() for item in value.split(",") if item.strip()]


def check_allowed(key, values, allowed):
    """
    A utility function to check that all values are allowed for a given key.
    """
    unknown = [value for value in values if value not in allowed]
    if unknown:
        raise IssueError(f"Unknown {key} value(s): {', '.join(unknown)}. "
                         f"Allowed: {', '.join(sorted(allowed))}.")


def load_json(path):
    """
    Load a JSON file from the given path.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data, separators=(",", ": ")):
    """
    Write a JSON file to the given path with the specified separators.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, separators=separators, ensure_ascii=False)
        f.write("\n")


def add_experiment(fields):
    """
    Converts the provided fields from the issue form into a new experiment entry in the controlled vocabulary (CV).
    """

    # Load the current controlled vocabulary (CV) from the JSON file.
    cv_root = load_json(CV_PATH)
    cv = cv_root["CV"]

    # Extract and validate the relevant metadata from the provided fields.
    experiment_id = require_identifier(fields, "experiment_id")
    if experiment_id in cv["experiment_id"]:
        raise IssueError(f"experiment_id '{experiment_id}' already exists.")

    activity_id = require(fields, "activity_id")
    check_allowed("activity_id", [activity_id], cv["activity_id"])

    required = split_list(require(fields, "required_model_components"))
    additional = split_list(fields.get("additional_allowed_model_components", ""))
    check_allowed("source_type", required + additional, cv["source_type"])

    parent_experiment_id = require(fields, "parent_experiment_id")
    if parent_experiment_id != "none" and parent_experiment_id not in cv["experiment_id"]:
        raise IssueError(f"parent_experiment_id '{parent_experiment_id}' is not a known experiment.")

    parent_activity_id = require(fields, "parent_activity_id")
    if parent_activity_id != "none":
        check_allowed("parent_activity_id", [parent_activity_id], cv["activity_id"])

    sub_experiment_id = require(fields, "sub_experiment_id")
    check_allowed("sub_experiment_id", [sub_experiment_id], cv["sub_experiment_id"])

    # Repack the metadata entries into the experiment_id dictionary within the CV.
    experiments = dict(cv["experiment_id"])
    experiments[experiment_id] = {
        "activity_id": [activity_id],
        "additional_allowed_model_components": additional,
        "experiment": require(fields, "experiment"),
        "experiment_id": experiment_id,
        "parent_activity_id": [parent_activity_id],
        "parent_experiment_id": [parent_experiment_id],
        "required_model_components": required,
        "sub_experiment_id": [sub_experiment_id],
    }
    cv["experiment_id"] = dict(sorted(experiments.items(), key=lambda kv: kv[0].lower()))

    # Write the updated CV back to the JSON file in a compact format.
    # UKCI_CV.json uses the compact "key":value style
    write_json(CV_PATH, cv_root, separators=(",", ":"))
    print(f"Added experiment_id '{experiment_id}' to {CV_PATH.relative_to(ROOT)}.")


def add_variable(fields):
    """
    Convert the provided fields from the issue form into a new variable entry in the
    respective controlled vocabulary (CV) and simultaneously update the variables file.
    """
    # Load the current controlled vocabulary (CV) from the JSON file.
    cv = load_json(CV_PATH)["CV"]

    # Extract and validate the relevant metadata from the provided fields.
    table = require_identifier(fields, "table")
    table_path = TABLES / f"UKCI_{table}.json"
    if table not in cv["table_id"] or not table_path.is_file():
        raise IssueError(f"Unknown table '{table}'.")

    out_name = require_identifier(fields, "out_name")
    table_data = load_json(table_path)
    if out_name in table_data["variable_entry"]:
        raise IssueError(f"Variable '{out_name}' already exists in {table_path.name}.")

    frequency = require(fields, "frequency")
    check_allowed("frequency", [frequency], cv["frequency"])

    modeling_realm = require(fields, "modeling_realm")
    check_allowed("modeling_realm", modeling_realm.split(), cv["realm"])

    positive = fields.get("positive", "").strip()
    if positive == "directionless":
        positive = ""
    check_allowed("positive", [positive], ["", "up", "down"])

    stream = require(fields, "stream")
    if not STREAM.match(stream):
        raise IssueError(f"'stream' must match {STREAM.pattern}, got '{stream}'.")

    # Repack the metadata entries into the variable_entry dictionary within the table data.
    table_data["variable_entry"][out_name] = {
        "frequency": frequency,
        "modeling_realm": modeling_realm,
        "standard_name": require(fields, "standard_name"),
        "units": require(fields, "units"),
        "cell_methods": fields.get("cell_methods", "").strip(),
        "cell_measures": fields.get("cell_measures", "").strip(),
        "long_name": require(fields, "long_name"),
        "comment": " ".join(fields.get("comment", "").split()),
        "dimensions": require(fields, "dimensions"),
        "out_name": out_name,
        "type": "real",
        "positive": positive,
        "valid_min": "",
        "valid_max": "",
        "ok_min_mean_abs": "",
        "ok_max_mean_abs": "",
    }
    # Write the updated table data back to the CVs JSON file.
    write_json(table_path, table_data)

    # Update the variables.txt file with the new variable entry.
    line = f"{table}/{out_name}:{stream}"
    existing = VARIABLES_TXT.read_text(encoding="utf-8") if VARIABLES_TXT.exists() else ""
    if line not in existing.splitlines():
        if existing and not existing.endswith("\n"):
            existing += "\n"
        VARIABLES_TXT.write_text(existing + line + "\n", encoding="utf-8")

    print(f"Added '{out_name}' to {table_path.relative_to(ROOT)} and {VARIABLES_TXT.relative_to(ROOT)}.")


# Handlers for different types of issue labels. Each handler corresponds to a specific label and is responsible
# for processing the issue accordingly.
HANDLERS = {
    "experiment_addition": add_experiment,
    "variable_addition": add_variable,
}


def main():
    """
    Main entry point for the script. It reads the GitHub event payload, determines the type of issue,
    and invokes the appropriate handler to process the issue.
    """
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise IssueError("GITHUB_EVENT_PATH is not set.")
    issue = load_json(event_path)["issue"]

    labels = {label["name"] for label in issue.get("labels", [])}
    matched = [name for name in HANDLERS if name in labels]
    if len(matched) != 1:
        raise IssueError(f"Issue must have exactly one of the labels: {', '.join(HANDLERS)}.")

    HANDLERS[matched[0]](parse_issue_body(issue.get("body") or ""))


if __name__ == "__main__":
    try:
        main()
    except IssueError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
