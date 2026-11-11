#!/usr/bin/env python3
"""Validate an offline CSV inventory and print a JSON summary."""

import csv
import json
import sys


class InventoryError(Exception):
    """An input validation failure with a safe, fixed message."""


def checked_lines(source):
    """Reject stray quotes that csv.reader's strict mode still tolerates."""
    state = "start"
    for line in source:
        for character in line:
            if state == "quoted":
                if character == '"':
                    state = "closed"
            elif state == "closed":
                if character == '"':
                    state = "quoted"
                elif character in ",\r\n":
                    state = "start"
                else:
                    raise InventoryError("Input contains malformed CSV quoting.")
            elif character == '"':
                if state != "start":
                    raise InventoryError("Input contains malformed CSV quoting.")
                state = "quoted"
            elif character in ",\r\n":
                state = "start"
            else:
                state = "unquoted"
        yield line
    if state == "quoted":
        raise InventoryError("Input contains malformed CSV quoting.")


def read_inventory(path):
    """Return a validated row count and total, without exposing input in errors."""
    # Avoid csv's small default field limit imposing an undocumented SKU limit.
    csv.field_size_limit(sys.maxsize)
    seen = set()
    total = 0
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(checked_lines(source), strict=True)
            header = next(reader, None)
            if header is None or len(header) != 2 or set(header) != {"sku", "quantity"}:
                raise InventoryError("Header must contain exactly sku and quantity.")
            sku_index = header.index("sku")
            quantity_index = header.index("quantity")
            for row in reader:
                if len(row) != 2:
                    raise InventoryError("Each row must contain exactly two fields.")
                sku = row[sku_index].strip()
                quantity = row[quantity_index].strip()
                if not sku:
                    raise InventoryError("SKU must not be empty.")
                if sku in seen:
                    raise InventoryError("SKUs must be unique.")
                if not quantity or any(char < "0" or char > "9" for char in quantity):
                    raise InventoryError("Quantity must contain decimal digits only.")
                total += int(quantity, 10)
                seen.add(sku)
    except UnicodeError:
        raise InventoryError("Input must be valid UTF-8.") from None
    except csv.Error:
        raise InventoryError("Input contains malformed CSV.") from None
    except OSError:
        raise InventoryError("Input file could not be read.") from None
    if not seen:
        raise InventoryError("Inventory must contain at least one row.")
    return {"rows": len(seen), "total_quantity": total}


def main(argv=None):
    """Write exactly one JSON result and return the corresponding exit status."""
    args = sys.argv[1:] if argv is None else argv
    # Quantities have no stated digit limit; permit Python's arbitrary-size ints.
    if hasattr(sys, "set_int_max_str_digits"):
        sys.set_int_max_str_digits(0)
    try:
        if len(args) != 1:
            raise InventoryError("Expected one CSV input file.")
        result = read_inventory(args[0])
    except InventoryError as error:
        print(json.dumps({"error": str(error)}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
