import os
import io
import uuid
import random
import pandas as pd
import streamlit as st
from datetime import datetime
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobServiceClient

MASTER_DATA = {
    "customers": [f"CUST_{i:04d}" for i in range(1, 21)],
    "dealers": [f"DLR_{i:03d}" for i in range(1, 11)],
    "products": [f"PROD_{i:04d}" for i in range(1, 51)],
    "plants": [f"PLNT_{i:02d}" for i in range(1, 5)],
    "stores": [f"STR_{i:02d}" for i in range(1, 6)],
    "materials": [f"MAT_{i:04d}" for i in range(1, 101)],
    "suppliers": [f"SPL_{i:03d}" for i in range(1, 16)]
}

def get_azure_blob_client():
    """Establishes an authenticated connection channel to your clean ADLS Gen2 lakehouse."""
    try:
        tenant_id = st.secrets["azure"]["AZURE_TENANT_ID"]
        client_id = st.secrets["azure"]["AZURE_CLIENT_ID"]
        client_secret = st.secrets["azure"]["AZURE_CLIENT_SECRET"]
        account_name = st.secrets["azure"]["STORAGE_ACCOUNT_NAME"]
        
        credential = ClientSecretCredential(tenant_id, client_id, client_secret)
        blob_service_client = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net", 
            credential=credential
        )
        return blob_service_client
    except Exception as e:
        print(f"Azure Connection Authentication Failed: {str(e)}")
        return None

def upload_dataframe_to_adls(df, dataset_name, batch_timestamp):
    """Streams data straight to the ADLS landing zone directory over HTTPS."""
    blob_service_client = get_azure_blob_client()
    if not blob_service_client:
        return False
        
    container_name = st.secrets["azure"]["CONTAINER_NAME"]
    
    # Structure enterprise path hierarchy partition syntax match: /raw/sales_orders/year=/month=/...
    ts_path = batch_timestamp.strftime("year=%Y/month=%m/day=%d/hour=%H")
    blob_path = f"landing/{dataset_name}/{ts_path}/BATCH_{batch_timestamp.strftime('%Y%m%d_%H%M')}_{dataset_name}.csv"
    
    # Convert memory DataFrame structure directly into a CSV bytes array buffer stream
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)
    
    try:
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_path)
        blob_client.upload_blob(csv_buffer.read(), overwrite=True)
        return True
    except Exception as e:
        print(f"Cloud Storage Ingestion Failure for target {blob_path}: {str(e)}")
        return False

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
        "duplicates_injected": 0,
        "azure_upload_status": "Pending"
    }
    
    # 1. SALES ORDERS GENERATION ENGINE
    sales_rows = []
    for _ in range(sales_count):
        is_bad = False
        sales_order_id = f"SO_{uuid.uuid4().hex[:8].upper()}"
        
        if random.random() < 0.10:
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

    df_sales = pd.DataFrame(sales_rows)
    if not df_sales.empty:
        duplicated_rows = df_sales.sample(n=4, random_state=random.randint(1,1000))
        df_sales = pd.concat([df_sales, duplicated_rows], ignore_index=True)
        batch_metrics["duplicates_injected"] += 4
        batch_metrics["total_generated"] += 4
        batch_metrics["bad_records"] += 4

    # 2. PURCHASE ORDERS GENERATION ENGINE
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

    # 3. INVENTORY SNAPSHOTS GENERATION ENGINE
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

    # Execute direct uploads straight to ADLS Gen2
    s_upload = upload_dataframe_to_adls(df_sales, "sales_orders", batch_timestamp)
    p_upload = upload_dataframe_to_adls(df_po, "purchase_orders", batch_timestamp)
    i_upload = upload_dataframe_to_adls(df_inv, "inventory_snapshots", batch_timestamp)
    
    if s_upload and p_upload and i_upload:
        batch_metrics["azure_upload_status"] = "Success"
    else:
        batch_metrics["azure_upload_status"] = "Failed"

    return batch_metrics, df_sales, df_po, df_inv

