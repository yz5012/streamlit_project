# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile
import os

# === Load Data from Cleaned_data.csv ===
@st.cache_data
def load_data():
    df = pd.read_csv("Cleaned_data.csv", parse_dates=['Created_date'])
    return df

df = load_data()

# === Neo4j Setup ===
database_name = "neo4j"
username = "neo4j"
password = "apan5400"  # Update if necessary
uri = "bolt://localhost:7687/" + database_name

driver = GraphDatabase.driver(uri, auth=(username, password))
session = driver.session()

st.success("✅ Successfully connected to Neo4j!")

# === Function to get network graph data ===
def get_zip_graph_data(selected_zip):
    query = """
    MATCH (z:Zip {code: $zip})-[r:HAS_COMPLAINT]->(c:ComplaintType)
    RETURN z.code AS zip, c.name AS complaint, r.count AS count
    ORDER BY count DESC
    """
    with session.begin_transaction() as tx:
        result = tx.run(query, zip=selected_zip)
        return [(record["zip"], record["complaint"], record["count"]) for record in result]

# === Streamlit Layout ===
st.title("📍 NYC Neighborhood Complaint Index (NCI)")

# Sidebar filter
with st.sidebar:
    st.header("Filter Options")
    zip_codes = df['Incident_zip'].dropna().unique()
    selected_zip = st.selectbox("Select ZIP Code", sorted(zip_codes))

# Filtered Data
filtered_df = df[df['Incident_zip'] == selected_zip]

st.subheader(f"Complaint Summary for ZIP {selected_zip}")

# Complaint counts
complaint_counts = filtered_df['Complaint_type'].value_counts().reset_index()
complaint_counts.columns = ['Complaint Type', 'Count']

# === Visualization Options ===
st.markdown("## 📊 Complaint Visualizations")

viz_option = st.selectbox(
    "Choose a visualization",
    ["Bar Chart", "Pie Chart", "Sunburst Chart", "Complaint Trend Over Time", "Top Boroughs (Overall)"]
)

if viz_option == "Bar Chart":
    fig = px.bar(
        complaint_counts,
        x="Complaint Type", y="Count",
        title="Complaint Types Distribution",
        labels={"Count": "Number of Complaints"},
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

elif viz_option == "Pie Chart":
    fig = px.pie(
        complaint_counts,
        names="Complaint Type", values="Count",
        title="Complaint Types Distribution",
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

elif viz_option == "Sunburst Chart":
    fig = px.sunburst(
        filtered_df,
        path=["Borough", "Complaint_type"],
        title="Complaint Breakdown: Borough ➔ Complaint Type",
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)

elif viz_option == "Complaint Trend Over Time":
    daily_trend = filtered_df.set_index('Created_date').resample('W').size().reset_index(name='count')
    fig = px.line(
        daily_trend,
        x="Created_date", y="count",
        title="Complaint Trend Over Time (Weekly Aggregated)",
        labels={"Created_date": "Date", "count": "Number of Complaints"},
        markers=True
    )
    st.plotly_chart(fig, use_container_width=True)

elif viz_option == "Top Boroughs (Overall)":
    borough_counts = df['Borough'].value_counts().reset_index()
    borough_counts.columns = ['Borough', 'Count']
    fig = px.bar(
        borough_counts,
        x="Borough", y="Count",
        title="Top Boroughs by Total Complaint Volume",
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

# === Raw Data Table ===
st.subheader("📄 Raw Complaint Records")
st.dataframe(filtered_df)

st.download_button(
    label="📥 Download Filtered Data as CSV",
    data=filtered_df.to_csv(index=False),
    file_name=f"complaints_{selected_zip}.csv",
    mime="text/csv"
)

# === Safe Neo4j Closing ===
session.close()
driver.close()
