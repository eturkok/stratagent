# Offline inventory checker

Run with Python 3; no packages or network access are needed:

```sh
python3 inventory.py INPUT.csv
```

Use a UTF-8 CSV file (an initial BOM is allowed) with exactly the headers `sku`
and `quantity`, in either order. For example:

```csv
sku,quantity
widget-a,2
widget-b,003
```

This prints `{"rows": 2, "total_quantity": 5}` and exits with status 0.
Surrounding whitespace in values is stripped. SKUs must then be nonempty and
unique (case sensitive). Quantities must contain only ASCII decimal digits
`0`–`9`; signs, fractions and exponent notation are rejected. Standard CSV
quoting supports commas, escaped double quotes and newlines inside quoted SKUs.

Invalid input prints one JSON object containing `error` to stdout and exits
with status 2. Errors never echo file contents. Missing or additional columns,
incomplete or blank rows, malformed quotes, empty inventories, invalid UTF-8
and unreadable files are rejected.

Run the local regression checks:

```sh
python3 -B -m unittest -v test_inventory.py
```
