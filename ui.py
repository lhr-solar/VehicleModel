import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from main import run_simulation, parse_yaml, get_param_units
from models.vehicle_model import VehicleModel
from models.rr import SCPRollingResistanceModel
from models.drag import SCPDragModel
from models.array import SCPArrayModel

st.set_page_config(
    page_title="Solar Car Simulator",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Solar Car Simulator")
st.markdown("---")

# Sidebar - Simulation Parameters
with st.sidebar:
    st.header(" Simulation Setup")
    
    # File upload or preset selection
    config_option = st.radio(
        "Configuration Source:",
        ["Use YAML File", "Manual Parameters"]
    )
    
    yaml_path = "params.yaml"  # Default path
    
    if config_option == "Use YAML File":
        yaml_file = st.file_uploader("Upload params.yaml", type=['yaml', 'yml'])
        if yaml_file is None:
            st.info("Using default params.yaml")
            yaml_path = "params.yaml"
        else:
            # Save uploaded file temporarily
            yaml_path = "/tmp/uploaded_params.yaml"
            with open(yaml_path, "wb") as f:
                f.write(yaml_file.read())
    
    st.markdown("---")
    
    # Parameter selection
    st.subheader("📊 Parameters to Log & Graph")
    available_params = [
        "velocity", "total_energy", "array_power", 
        "distance", "drag_force", "rr_force"
    ]
    
    selected_params = st.multiselect(
        "Select parameters:",
        available_params,
        default=["velocity", "total_energy", "array_power"]
    )
    
    st.markdown("---")
    
    # Run button
    run_button = st.button("🚀 Run Simulation", type="primary", use_container_width=True)

# Main content
if run_button:
    if not selected_params:
        st.error("Please select at least one parameter to log.")
    else:
        with st.spinner("Running simulation..."):
            # Initialize and run simulation
            m = VehicleModel(parse_yaml(yaml_path))
            m.add_model(SCPRollingResistanceModel())
            m.add_model(SCPDragModel())
            m.add_model(SCPArrayModel())
            
            # Run simulation
            df = run_simulation(m, selected_params)
            units_map = get_param_units(m, selected_params)
            
            # Store in session state
            st.session_state['df'] = df
            st.session_state['units_map'] = units_map
            st.session_state['selected_params'] = selected_params
        
        st.success("✅ Simulation complete!")

# Display results if available
if 'df' in st.session_state:
    df = st.session_state['df']
    units_map = st.session_state['units_map']
    selected_params = st.session_state['selected_params']
    
    # Summary metrics
    st.header("📈 Summary")
    cols = st.columns(len(selected_params))
    for i, param in enumerate(selected_params):
        with cols[i]:
            final_value = df[param].iloc[-1]
            unit = units_map.get(param, "")
            st.metric(
                label=f"{param}",
                value=f"{final_value:.2f} {unit}",
                delta=f"{df[param].iloc[-1] - df[param].iloc[0]:.2f}"
            )
    
    st.markdown("---")
    
    # Interactive graphs
    st.header("📊 Interactive Graphs")
    
    # Tabs for different parameters
    tabs = st.tabs(selected_params)
    
    for i, param in enumerate(selected_params):
        with tabs[i]:
            unit = units_map.get(param, "")
            
            # Create Plotly figure
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=df[param],
                mode='lines+markers',
                name=param,
                line=dict(color='#B923AA', width=2),
                marker=dict(size=4)
            ))
            
            fig.update_layout(
                title=f"{param} Over Time",
                xaxis_title="Time",
                yaxis_title=f"{param} ({unit})" if unit else param,
                hovermode='x unified',
                height=500
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Data table
    with st.expander("📋 View Raw Data"):
        st.dataframe(df.drop(columns=['datetime']), use_container_width=True)
    
    # Download buttons
    col1, col2 = st.columns(2)
    with col1:
        csv = df.drop(columns=['datetime']).to_csv(index=False)
        st.download_button(
            label="💾 Download CSV",
            data=csv,
            file_name="simulation_results.csv",
            mime="text/csv"
        )
    
    with col2:
        st.download_button(
            label="📥 Download Report",
            data="Report feature coming soon!",
            file_name="simulation_report.pdf",
            mime="application/pdf",
            disabled=True
        )

else:
    # Welcome screen
    st.info("👈 Configure parameters in the sidebar and click **Run Simulation** to start!")
    
    st.markdown("""
    ### Features:
    - 📊 Interactive graphs with zoom, pan, and hover
    - 🔄 Compare multiple scenarios
    - 💾 Export results as CSV
    - ⚡ Real-time parameter adjustment
    - 📈 Energy flow visualization
    """)