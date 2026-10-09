import os
import uuid
import random
import pandas as pd
from datetime import datetime

MASTER_DATA = {
    "customers": [f"CUST_{i:04d}" for i in range(1, 21)],
    "dealers": [f"DLR_{i:03d}" for i in range(1, 11)],
    "products": [f"PROD_{i:04d}" for i in range(1, 51)],
    "plants": [f"PLNT_{i:02d}" for i in range(1, 5)],
    "stores": [f"STR_{i:02d}" for i in range(1, 6)],
    "materials": [f"MAT_{i:04d}" for i in range(1, 101)],
    "suppliers": [f"SPL_{i:03d}" for i in range(1, 16)]
}

def generate_hourly_batch(batch_timestamp=None):
    if not batch_timestamp:
        batch_timestamp = datetime.utcnow()
        
    sales_count = 50
    purchase_count = 30
    inventory_count = 20
    
    batch_metrics = {
        "timestamp": batch_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "total_generated": 100,
        "good_records": 0,
        "bad_records": 0,
        "null_injected": 0,
        "formatting_drift_injected": 0,
        "duplicates_injected": 0
    }
    
    # 1. SALES ORDERS
    sales_rows = []
    for _ in range(sales_count):
        is_bad = False
        sales_order_id = f"SO_{uuid.uuid4().hex[:8].upper()}"
        
        if random.random() < 0.10: # Increased to ensure errors appear clearly
            sales_order_id = None
            batch_metrics["null_injected"] += 1
            is_bad = True
            
        customer_id = random.choice(MASTER_DATA["customers"])
        if random.random() < 0.05:
            customer_id = ""
            batch_metrics["null_injected"] += 1
            is_bad = True
            
        if random.random() < 0.10:
            sales = random.choice(["Executive_Red", "Error_Flag", "Bad_Value"])
            batch_metrics["formatting_drift_injected"] += 1
            is_bad = True
        else:
            sales = round(random.uniform(500.0, 15000.0), 2)
            
        row = {
            "sales_order_id": sales_order_id,
            "order_line_id": random.randint(1, 4),
            "order_date": batch_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": customer_id,
            "dealer_id": random.choice(MASTER_DATA["dealers"]),
            "store_id": random.choice(MASTER_DATA["stores"]),
            "product_id": random.choice(MASTER_DATA["products"]),
            "plant_id": random.choice(MASTER_DATA["plants"]),
            "quantity": random.randint(1, 50),
            "sales": sales,
            "last_modified_at": batch_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
        sales_rows.append(row)
        if is_bad: batch_metrics["bad_records"] += 1
        else: batch_metrics["good_records"] += 1

    # FORCE DUPLICATES: Duplicate exactly 4 rows on every run
    df_sales = pd.DataFrame(sales_rows)
    if not df_sales.empty:
        duplicated_rows = df_sales.sample(n=4, random_state=random.randint(1,1000))
        df_sales = pd.concat([df_sales, duplicated_rows], ignore_index=True)
        batch_metrics["duplicates_injected"] += 4
        batch_metrics["total_generated"] += 4
        batch_metrics["bad_records"] += 4

    # 2. PURCHASE ORDERS
    po_rows = []
    for _ in range(purchase_count):
        is_bad = False
        purchase_order_id = f"PO_{uuid.uuid4().hex[:8].upper()}"
        if random.random() < 0.08:
            purchase_order_id = None
            batch_metrics["null_injected"] += 1
            is_bad = True
            
        row = {
            "purchase_order_id": purchase_order_id,
            "order_date": batch_timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "supplier_id": random.choice(MASTER_DATA["suppliers"]),
            "plant_id": random.choice(MASTER_DATA["plants"]),
            "material_id": random.choice(MASTER_DATA["materials"]),
            "product_id": random.choice(MASTER_DATA["products"]),
            "ordered_quantity": random.randint(100, 5000),
            "last_modified_at": batch_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
        po_rows.append(row)
        if is_bad: batch_metrics["bad_records"] += 1
        else: batch_metrics["good_records"] += 1
    df_po = pd.DataFrame(po_rows)

    # 3. INVENTORY SNAPSHOTS
    inv_rows = []
    for _ in range(inventory_count):
        q_on_hand = random.randint(500, 10000)
        q_reserved = random.randint(0, 400)
        row = {
            "inventory_snapshot_id": f"INV_{uuid.uuid4().hex[:8].upper()}",
            "snapshot_date": batch_timestamp.strftime("%Y-%m-%d"),
            "plant_id": random.choice(MASTER_DATA["plants"]),
            "product_id": random.choice(MASTER_DATA["products"]),
            "quantity_on_hand": q_on_hand,
            "quantity_reserved": q_reserved,
            "quantity_available": q_on_hand - q_reserved,
            "last_modified_at": batch_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
        inv_rows.append(row)
        batch_metrics["good_records"] += 1
    df_inv = pd.DataFrame(inv_rows)

    # Write out local files
    base_dir = "data_output"
    ts_path = batch_timestamp.strftime("year=%Y/month=%m/day=%d/hour=%H")
    for name, df in [("sales_orders", df_sales), ("purchase_orders", df_po), ("inventory_snapshots", df_inv)]:
        target_path = os.path.join(base_dir, name, ts_path)
        os.makedirs(target_path, exist_ok=True)
        df.to_csv(os.path.join(target_path, f"{name}_batch.csv"), index=False)

    return batch_metrics, df_sales, df_po, df_inv
