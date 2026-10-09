import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
import json
import os
from generator import generate_hourly_batch

METRICS_LOG_FILE = "generation_history_log.json"

st.set_page_config(page_title="PASA Data Quality Center", layout="wide")

# Force an elegant Dark-Tech UI Color Override
# Force an elegant Dark-Tech UI Color Override
st.markdown("""
    <style>
        .stApp { background-color: #0E1117; color: #E0E0E0; }
        div[data-testid="stMetricValue"] { color: #3B82F6 !important; font-weight: bold; }
        .stButton>button { background-color: #1F2937; color: white; border: 1px solid #3B82F6; border-radius: 6px; }
        .stButton>button:hover { background-color: #3B82F6; color: white; }
    </style>
""", unsafe_allow_html=True) # <-- Changed from unsafe_index=True


def load_history_logs():
    if os.path.exists(METRICS_LOG_FILE):
        with open(METRICS_LOG_FILE, "r") as f: return json.load(f)
    return []

def append_history_log(metrics):
    logs = load_history_logs()
    logs.append(metrics)
    with open(METRICS_LOG_FILE, "w") as f: json.dump(logs, f, indent=4)

st.title("🏭 PASA Production Pipeline Dashboard")
st.markdown("### `pasa_supply_chain` // Data Drift & Duplication Operational Terminal")
st.write("---")

col_btn1, _ = st.columns([2, 5])
with col_btn1:
    if st.button("🚀 Trigger Next Hourly Batch Execution"):
        current_logs = load_history_logs()
        if not current_logs:
            for i in range(8, 0, -1):
                simulated_time = datetime.utcnow() - timedelta(hours=i)
                m, _, _, _ = generate_hourly_batch(simulated_time)
                append_history_log(m)
        metrics, _, _, _ = generate_hourly_batch()
        append_history_log(metrics)
        st.success("Batch successfully committed!")

history_data = load_history_logs()

if history_data:
    df_history = pd.DataFrame(history_data)
    latest_run = history_data[-1]
    
    # Summary Metrics Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Rows Ingested", f"{latest_run['total_generated']} rows")
    kpi2.metric("Clean Records (Good)", f"{latest_run['good_records']} rows")
    kpi3.metric("Anomalies Captured (Bad)", f"{latest_run['bad_records']} rows")
    kpi4.metric("Duplicates Injected", f"{latest_run['duplicates_injected']} rows")
    
    st.write("---")
    
    # Chart 1: Altair Grouped Side-by-Side Clean vs Bad volume Chart
    st.markdown("#### 📈 Chronological Hourly Ingestion Volume")
    df_melted_vol = df_history.melt(id_vars=["timestamp"], value_vars=["good_records", "bad_records"], 
                                    var_name="Data Type", value_name="Record Count")
    
    vol_chart = alt.Chart(df_melted_vol).mark_bar().encode(
        x=alt.X("timestamp:N", title="Execution Timestamp"),
        y=alt.Y("Record Count:Q", title="Total Records"),
        color=alt.Color("Data Type:N", scale=alt.Scale(domain=["good_records", "bad_records"], range=["#10B981", "#EF4444"])),
        xOffset="Data Type:N"
    ).properties(height=350).interactive()
    
    st.altair_chart(vol_chart, use_container_width=True)
    
    # Chart 2: Structural Breakdown of System Issues
    st.markdown("#### 🔬 Detailed Structural Issue Breakdown (Nulls, Drift & Duplicates)")
    df_melted_drift = df_history.melt(id_vars=["timestamp"], value_vars=["null_injected", "formatting_drift_injected", "duplicates_injected"],
                                     var_name="Anomaly Type", value_name="Incident Count")
    
    drift_chart = alt.Chart(df_melted_drift).mark_line(point=True).encode(
        x=alt.X("timestamp:N", title="Execution Timestamp"),
        y=alt.Y("Incident Count:Q", title="Incidents Logged"),
        color=alt.Color("Anomaly Type:N", scale=alt.Scale(range=["#3B82F6", "#F59E0B", "#EC4899"])),
        tooltip=["timestamp", "Anomaly Type", "Incident Count"]
    ).properties(height=350).interactive()
    
    st.altair_chart(drift_chart, use_container_width=True)
    
    st.write("---")
    st.markdown("#### 📄 Audit Log Extract")
    st.dataframe(df_history.tail(5), use_container_width=True)
else:
    st.warning("⚠️ No metadata logs found. Trigger a batch execution above to view analytics visualization metrics.")
