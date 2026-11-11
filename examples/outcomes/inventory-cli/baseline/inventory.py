#!/usr/bin/env python3
"""Validate a UTF-8 inventory CSV and print a JSON summary."""

import csv
import io
import json
import re
import sys


class InventoryError(Exception):
    """An input error whose message is safe to display."""


def validate_quoting(text):
    """Reject stray quotes as well as unterminated quoted CSV fields.

    csv.reader(strict=True) accepts quotes inside unquoted fields, so check
    that part of CSV syntax explicitly before handing parsing to csv.reader.
    """
    state = "start"
    for character in text:
        if state == "quoted":
            if character == '"':
                state = "closed"
        elif state == "closed":
            if character == '"':
                state = "quoted"
            elif character == "," or character in "\r\n":
                state = "start"
            else:
                raise InventoryError("Invalid CSV quoting.")
        elif character == '"':
            if state != "start":
                raise InventoryError("Invalid CSV quoting.")
            state = "quoted"
        elif character == "," or character in "\r\n":
            state = "start"
        else:
            state = "unquoted"
    if state == "quoted":
        raise InventoryError("Invalid CSV quoting.")


def summarize(path):
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as source:
            text = source.read()
    except UnicodeDecodeError:
        raise InventoryError("Input must be valid UTF-8.") from None
    except (OSError, ValueError):
        raise InventoryError("Unable to read input file.") from None

    validate_quoting(text)
    # Do not impose csv's small default limit on otherwise valid field values.
    field_limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(field_limit)
            break
        except OverflowError:
            field_limit //= 10
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader, None)
        if header is None or len(header) != 2 or set(header) != {"sku", "quantity"}:
            raise InventoryError("Expected exactly the columns sku and quantity.")
        sku_index = header.index("sku")
        quantity_index = header.index("quantity")
        skus = set()
        total = 0
        for row in reader:
            if len(row) != 2:
                raise InventoryError("Every row must contain exactly two fields.")
            sku = row[sku_index].strip()
            quantity = row[quantity_index].strip()
            if not sku:
                raise InventoryError("SKUs must be nonempty.")
            if sku in skus:
                raise InventoryError("SKUs must be unique.")
            if re.fullmatch(r"[0-9]+", quantity) is None:
                raise InventoryError("Quantities must be nonnegative decimal whole numbers.")
            skus.add(sku)
            total += int(quantity)
    except csv.Error:
        raise InventoryError("Invalid CSV format.") from None
    if not skus:
        raise InventoryError("Inventory must contain at least one row.")
    return {"rows": len(skus), "total_quantity": total}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    # Python 3.11+ otherwise caps conversion of long, valid decimal integers.
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    try:
        if len(argv) != 1:
            raise InventoryError("Expected one CSV file path.")
        result = summarize(argv[0])
    except InventoryError as error:
        print(json.dumps({"error": str(error)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
