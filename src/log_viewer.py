#!/usr/bin/env python
"""
Standalone Log Viewer for GraphRAG Contract Review
This is a minimal Streamlit app that just shows the log viewer UI.
"""

import os
import sys
import base64
import streamlit as st
from typing import List, Optional

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import logger functions from the local logger module
from logger import (
    get_logger,
    get_log_file_paths,
    read_log_file
)

# Initialize logger
log_viewer_logger = get_logger("log_viewer")

def get_log_download_link_html(log_file_path: str) -> str:
    """Generate an HTML download link for a log file"""
    try:
        with open(log_file_path, "r", encoding='utf-8') as file:
            log_content_bytes = file.read().encode('utf-8')
        filename = os.path.basename(log_file_path)
        b64 = base64.b64encode(log_content_bytes).decode()
        return f'<a href="data:text/plain;charset=utf-8;base64,{b64}" download="{filename}" class="download-button">Download {filename}</a>'
    except Exception as e:
        log_viewer_logger.error(f"Error creating download link for {os.path.basename(log_file_path)}: {str(e)}")
        return ""

# Configure Streamlit page
st.set_page_config(
    page_title="GraphRAG Log Viewer",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Add styling for the log viewer
log_specific_css = """
    .download-button {
        display: inline-block; padding: 8px 12px; background-color: #4a86e8;
        color: white !important; text-decoration: none !important; border-radius: 4px;
        font-weight: 500; border: none; cursor: pointer;
    }
    .download-button:hover { background-color: #3a76d8; color: white !important; text-decoration: none !important; }
    a.download-button, a.download-button:visited { color: white !important; text-decoration: none !important; }
    .hide-streamlit-markers div[data-testid="stToolbar"] {
        display: none;
    }
    .hide-streamlit-markers footer {
        display: none;
    }
    .hide-streamlit-markers #MainMenu {
        display: none;
    }
    section[data-testid="stSidebar"] {
        display: none;
    }
"""

st.markdown(f"<style>{log_specific_css}</style>", unsafe_allow_html=True)
st.markdown('<div class="hide-streamlit-markers"></div>', unsafe_allow_html=True)

# Main log viewer UI
log_files_available = get_log_file_paths(max_count=20)

if not log_files_available:
    st.info("No log files found. Check that the logs directory exists in the project folder.")
else:
    log_file_options = {os.path.basename(f): f for f in log_files_available}
    
    # Initialize session state for selected file and number of lines
    if 'selected_log_file' not in st.session_state or st.session_state.selected_log_file not in log_file_options.values():
        st.session_state.selected_log_file = log_files_available[0]
    if 'lines_to_show' not in st.session_state:
        st.session_state.lines_to_show = 100
    
    # Single line for all controls using columns
    col1, col2, col3 = st.columns([5, 2, 1])
    
    with col1:
        selected_log_basename = st.selectbox(
            "Select log file",
            options=list(log_file_options.keys()),
            index=list(log_file_options.keys()).index(os.path.basename(st.session_state.selected_log_file)) 
                if os.path.basename(st.session_state.selected_log_file) in log_file_options.keys() else 0,
            label_visibility="collapsed"
        )
        # Update session state
        st.session_state.selected_log_file = log_file_options[selected_log_basename]
    
    with col2:
        lines_to_show = st.number_input(
            "Number of lines",
            min_value=10, max_value=1000,
            value=st.session_state.lines_to_show, step=10,
            key="log_viewer_lines_input",
            label_visibility="collapsed"
        )
        # Update session state
        st.session_state.lines_to_show = lines_to_show
    
    with col3:
        st.button("🔄", key="log_viewer_refresh_button")
    
    # Display log content
    log_content = read_log_file(
        st.session_state.selected_log_file,
        max_lines=st.session_state.lines_to_show
    )
    
    # Show log content
    st.code(log_content, language='text', line_numbers=False)
    
    # Add download link
    download_html = get_log_download_link_html(st.session_state.selected_log_file)
    if download_html:
        st.markdown(download_html, unsafe_allow_html=True)
    else:
        st.warning(f"Could not generate download link for {selected_log_basename}.")
