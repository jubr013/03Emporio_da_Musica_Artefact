"""One-off data exploration script. Prints the checks summarized in docs/data_exploration.md.

Run from the repo root:  python scripts/explore_data.py
"""
import json
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"

products = pd.read_csv(DATA / "products.csv")
categories = pd.read_csv(DATA / "categories.csv")
customers = pd.read_csv(DATA / "customers.csv")
orders = pd.read_csv(DATA / "orders.csv")
items = pd.read_csv(DATA / "order_items.csv")
promos = pd.read_csv(DATA / "promotions.csv")

print("== Shapes ==")
for name, df in [("products", products), ("categories", categories), ("customers", customers),
                 ("orders", orders), ("order_items", items), ("promotions", promos)]:
    print(f"{name:12} {df.shape}")

print("\n== Dtypes (products, orders) ==")
print(products.dtypes, "\n")
print(orders.dtypes)

print("\n== Nulls per column ==")
for name, df in [("products", products), ("customers", customers), ("orders", orders)]:
    nulls = df.isna().sum()
    print(name, dict(nulls[nulls > 0]))

print("\n== Products: status / stock ==")
print(products["status"].value_counts().to_dict())
print("stock == 0:", products.loc[products["stock_quantity"] == 0, ["product_id", "name", "status"]].values.tolist())
print("duplicate product_id:", products["product_id"].duplicated().sum())

print("\n== Products per category ==")
counts = products.groupby("category_id").size()
print(categories.assign(n_products=categories["category_id"].map(counts).fillna(0).astype(int))[["category_id", "name", "n_products"]].to_string(index=False))

print("\n== Specs keys by category (all specs parse as JSON?) ==")
specs = products["specs"].apply(json.loads)  # raises if any row is not valid JSON
for cat_id, group in products.assign(keys=specs.apply(lambda d: tuple(sorted(d)))).groupby("category_id"):
    print(cat_id, group["keys"].unique().tolist())

print("\n== Promotions ==")
print("active:", promos.loc[promos["is_active"] == 1, ["promotion_id", "product_id", "discount_percent", "description"]].values.tolist())
print("products with >1 promo row:", promos["product_id"][promos["product_id"].duplicated()].unique().tolist())
print("promo product_ids missing from catalog:", sorted(set(promos["product_id"]) - set(products["product_id"])))

print("\n== Orders ==")
print(orders["status"].value_counts().to_dict())
print(orders["payment_method"].value_counts().to_dict())
print("date range:", orders["order_date"].min(), "->", orders["order_date"].max())

print("\n== Order total vs sum(item price * qty) ==")
merged = items.merge(products[["product_id", "price_brl"]], on="product_id", how="left")
merged["line_total"] = merged["quantity"] * merged["price_brl"]
calc = merged.groupby("order_id")["line_total"].sum().rename("calc_total")
check = orders.set_index("order_id")[["total_brl"]].join(calc)
print(check[(check["total_brl"] - check["calc_total"]).abs() > 0.01])

print("\n== Order items referencing non-active products ==")
print(items.merge(products[["product_id", "name", "status"]], on="product_id")
      .query("status != 'active'").to_string(index=False))

print("\n== Customers ==")
print("duplicate emails:", customers.loc[customers["email"].duplicated(keep=False), ["customer_id", "name", "email"]].values.tolist())
print("duplicate phones:", customers.loc[customers["phone"].duplicated(keep=False), ["customer_id", "name", "phone"]].values.tolist())
print("customers with orders:", sorted(orders["customer_id"].unique().tolist()))
print("cities:", customers["city"].value_counts().to_dict())

print("\n== Tracking code format (BR + 9 alnum + BR) ==")
codes = orders["tracking_code"].dropna()
print("all match:", codes.str.fullmatch(r"BR[A-Z0-9]{9}BR").all())
