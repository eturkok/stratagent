# Usage

Requires Python 3; no packages or network access are needed.

```sh
python3 inventory.py INPUT.csv
```

Use UTF-8 CSV (an initial BOM is accepted). The header must contain exactly
`sku` and `quantity`, in either order. Each subsequent row must have both
fields. Values are trimmed; SKUs must be nonempty and unique after trimming.
Quantities must contain only decimal digits `0`–`9` (leading zeros are allowed).
At least one inventory row is required. Standard CSV quoting, escaped quotes,
and quoted fields spanning lines are supported.

Example input:

```csv
sku,quantity
apple,12
pear,3
```

Success prints `{"rows": 2, "total_quantity": 15}` and exits 0.
Invalid input prints one JSON object containing `error` and exits 2.
Error messages never echo input values or paths. All CLI output goes to stdout.

Run the local checks with:

```sh
python3 -m unittest -v test_inventory.py
```
