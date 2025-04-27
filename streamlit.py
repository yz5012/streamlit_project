# app.py

import streamlit as st
import pandas as pd
import plotly.express as px
from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components
import tempfile
import os

# === Neo4j Setup ===
database_name = "neo4j"
username = "neo4j"
password = "apan5400"  # Update if necessary
uri = "bolt://localhost:7687/" + database_name

driver = GraphDatabase.driver(uri, auth=(username, password))
session = driver.session()

st.success("✅ Successfully connected to Neo4j!")

# === Function to load data from Neo4j instead of CSV ===
@st.cache_data
def load_data_from_neo4j():
    query = """
    MATCH (z:Zip)-[r:HAS_COMPLAINT]->(c:ComplaintType)
    OPTIONAL MATCH (z)-[:LOCATED_IN]->(b:Borough)
    RETURN z.code AS Incident_zip,
           c.type AS Complaint_type,
           b.name AS Borough,
           r.count AS count
    """
    with session.begin_transaction() as tx:
        result = tx.run(query)
        records = result.data()
    df = pd.DataFrame(records)
    
    # Fill missing Boroughs if any
    df['Borough'] = df['Borough'].fillna('UNKNOWN')
    
    # Create dummy Created_date for testing trend if needed
    df['Created_date'] = pd.date_range(start='2023-01-01', periods=len(df), freq='D')

    return df

df = load_data_from_neo4j()

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
st.title("📍 NYC Neighborhood Complaint Index (NCI) (Neo4j Live)")

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

# === Neo4j Network Graph ===
st.subheader("🌐 Complaint Network Graph (Neo4j)")

graph_data = get_zip_graph_data(selected_zip)

if graph_data:
    g = Network(height="400px", width="100%", notebook=False)
    g.add_node(selected_zip, label=f"ZIP: {selected_zip}", color="blue")
    for zip_code, complaint_type, count in graph_data:
        g.add_node(complaint_type, label=complaint_type, color="orange")
        g.add_edge(zip_code, complaint_type, value=count, title=f"{count} complaints")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        g.show(tmp_file.name)
        HtmlFile = open(tmp_file.name, 'r', encoding='utf-8')
        components.html(HtmlFile.read(), height=450)
        HtmlFile.close()
        os.remove(tmp_file.name)
else:
    st.warning("⚠️ No graph data available for this ZIP code in Neo4j.")

# === Safe Neo4j Closing ===
session.close()
driver.close()
