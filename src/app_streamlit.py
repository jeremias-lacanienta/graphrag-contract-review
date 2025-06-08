"""
GraphRAG Contract Review Streamlit Application

A web interface for reviewing and querying contract data using neo4j_graphrag.
This provides a user-friendly frontend to the GraphRAG contract review system.
"""

import os
import sys
import json
import asyncio
import streamlit as st
from typing import Any, Dict, List, Union
import subprocess
from dotenv import load_dotenv

# Add the parent directory to sys.path to enable imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import services
from ContractService import ContractSearchService
from AgreementSchema import ClauseType
from template_renderer import format_result as render_template

# Load environment variables
load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="GraphRAG Contract Review",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #4a86e8;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #6c757d;
        margin-bottom: 1rem;
    }
    .result-container {
        background-color: #f5f5f5;
        padding: 20px;
        border-radius: 5px;
        margin-top: 20px;
        margin-bottom: 20px;
        white-space: pre-wrap;
    }
    .separator {
        margin-top: 20px;
        margin-bottom: 20px;
        border-bottom: 1px solid #ddd;
    }
    /* Toggle Button Styling */
    div.stButton > button {
        width: 100%;
        border-radius: 5px;
        border: 1px solid #ddd;
        padding: 5px 10px; /* Reduced padding to minimize space */
        text-align: left;
        background-color: #f8f9fa;
        transition: all 0.3s;
        margin-bottom: 0px; /* Removed spacing between buttons */
    }
    /* Reduce spacing in sidebar button containers */
    section[data-testid="stSidebar"] div.stButton {
        margin-top: 0px;
        margin-bottom: 0px;
        padding-top: 0px;
        padding-bottom: 0px;
    }
    div.stButton > button:hover {
        background-color: #e9ecef;
        border-color: #bbb;
    }
    /* Style for selected button using session state */
    div.stButton > button[kind="secondary"]:focus {
        box-shadow: none;
    }
    /* Primary button styling for active state */
    div.stButton > button[kind="primary"] {
        background-color: #4a86e8;
        color: white;
        border-color: #3a76d8;
        font-weight: 500;
        padding: 5px 10px 5px 15px; /* Match the reduced padding */
    }
    div.stButton > button[kind="primary"]::before {
        content: "• ";
        font-size: 20px;
        position: relative;
        top: 1px;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #3a76d8;
        border-color: #2a66c8;
    }
    /* Style for the suggestion info box */
    div[data-testid="stInfo"] {
        background-color: #e8f0fe;
        border-left-color: #4a86e8;
        padding: 10px;
        margin-bottom: 10px;
        border-radius: 4px;
    }
    /* Center certain elements */
    .centered-text {
        text-align: center;
        margin-left: auto;
        margin-right: auto;
        display: block;
    }
</style>
""", unsafe_allow_html=True)

# Define constants
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')

# Initialize session state for chat history
if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'service' not in st.session_state:
    st.session_state.service = None

async def initialize_service():
    """Initialize the ContractSearchService"""
    if not st.session_state.service:
        try:
            service = ContractSearchService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
            st.session_state.service = service
            return service
        except Exception as e:
            st.error(f"Error initializing service: {str(e)}")
            st.error("Make sure Neo4j is running and your environment variables are set correctly.")
            return None
    return st.session_state.service

def run_async(coroutine):
    """Run an async function from Streamlit"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)

# Main header
st.markdown("<h1 class='main-header'>GraphRAG Contract Review System</h1>", unsafe_allow_html=True)
st.markdown("<p>Interactive interface for exploring and analyzing contracts using graph-based retrieval</p>", unsafe_allow_html=True)

# Command definitions based on run_graphrag.sh
commands = [
    {
        "name": "Get Contract by ID",
        "command": "get_contract",
        "description": "Retrieve a specific contract by its ID",
        "args_description": "Contract ID (e.g., 3)",
        "example": "3"
    },
    {
        "name": "Get Contracts by Party",
        "command": "get_contracts_by_party",
        "description": "Find all contracts involving a specific organization",
        "args_description": "Organization name (e.g., 'Birch First Global Investments Inc.')",
        "example": "Birch First Global Investments Inc."
    },
    {
        "name": "Get Contracts with Clause Type",
        "command": "get_contracts_with_clause_type",
        "description": "Find contracts containing a specific clause type",
        "args_description": "Clause type (e.g., 'IP Ownership Assignment')",
        "example": "IP Ownership Assignment"
    },
    {
        "name": "Get Contracts without Clause",
        "command": "get_contracts_without_clause",
        "description": "Find contracts that don't contain a specific clause type",
        "args_description": "Clause type (e.g., 'Arbitration')",
        "example": "Arbitration"
    },
    {
        "name": "Find Similar Text in Contracts",
        "command": "get_contracts_similar_text",
        "description": "Find contracts with clauses similar to the specified text",
        "args_description": "Text to search for (e.g., 'payment terms')",
        "example": "payment terms"
    },
    {
        "name": "Get Contract Excerpts",
        "command": "get_contract_excerpts",
        "description": "Get all clause excerpts from a specific contract",
        "args_description": "Contract ID (e.g., 3)",
        "example": "3"
    },
    {
        "name": "Answer Aggregation Question",
        "command": "answer_aggregation_question",
        "description": "Get insights by asking a question about the contract database",
        "args_description": "Question (e.g., 'What are the incorporation states for parties in the Master Franchise Agreement?')",
        "example": "What are the incorporation states for parties in the Master Franchise Agreement?"
    },
    {
        "name": "General Search",
        "command": "search",
        "description": "Search for any terms across all contracts",
        "args_description": "Search terms (e.g., 'confidentiality')",
        "example": "confidentiality"
    }
]

# Sidebar with command options

# Initialize the selected command in session state if not already set
if 'selected_command' not in st.session_state:
    st.session_state.selected_command = commands[0]["name"]

# Initialize default input text in session state
if 'default_input' not in st.session_state:
    st.session_state.default_input = commands[0]["example"]

# Generate the styled toggle buttons
for cmd in commands:
    # Check if this button should be active based on the session state
    is_active = st.session_state.selected_command == cmd["name"]
    
    # Create the button with the proper styling
    if st.sidebar.button(
        cmd["name"], 
        key=f"toggle_{cmd['name']}", 
        use_container_width=True,
        type="primary" if is_active else "secondary"
    ):
        # Update the session state when this button is clicked
        st.session_state.selected_command = cmd["name"]
        # Set the default input text to the example for this command
        st.session_state.default_input = cmd["example"]
        st.rerun()

# Get the selected command details
selected_cmd = next((cmd for cmd in commands if cmd["name"] == st.session_state.selected_command), None)

# Display information about the selected command
st.sidebar.markdown("---")
st.sidebar.markdown(f"### {selected_cmd['name']}")
st.sidebar.markdown(f"{selected_cmd['description']}")
st.sidebar.markdown(f"**Input format**: {selected_cmd['args_description']}")

# Display example for the selected command
st.sidebar.markdown("**Example**:")
st.sidebar.code(selected_cmd['example'], language=None)

# Chat-like input interface
for message in st.session_state.messages:
    if message["role"] == "user":
        st.chat_message("user").write(message["content"])
    else:
        st.chat_message("assistant").write(message["content"])

# Input field for command arguments (without default value as it's not supported)
user_input = st.chat_input("Enter your command input here...")

if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.chat_message("user").write(user_input)
    
    # Initialize the service
    service = run_async(initialize_service())
    
    if service:
        try:
            # Process based on command type
            command = selected_cmd["command"]
            result = None
            
            with st.spinner(f"Processing {selected_cmd['name']}..."):
                # Process command based on type
                if command == "get_contract":
                    contract_id = int(user_input)
                    result = run_async(service.get_contract(contract_id))
                
                elif command == "get_contracts_by_party":
                    org = user_input
                    result = run_async(service.get_contracts(org))
                
                elif command == "get_contracts_with_clause_type":
                    clause_type = ClauseType[user_input] if hasattr(ClauseType, user_input) else user_input
                    result = run_async(service.get_contracts_with_clause_type(clause_type))
                
                elif command == "get_contracts_without_clause":
                    clause_type = ClauseType[user_input] if hasattr(ClauseType, user_input) else user_input
                    result = run_async(service.get_contracts_without_clause(clause_type))
                
                elif command == "get_contracts_similar_text":
                    result = run_async(service.get_contracts_similar_text(user_input))
                
                elif command == "get_contract_excerpts":
                    contract_id = int(user_input)
                    result = run_async(service.get_contract_excerpts(contract_id))
                
                elif command == "answer_aggregation_question":
                    question = user_input
                    result = run_async(service.answer_aggregation_question(question))
                
                elif command == "search":
                    # Default search behavior
                    result = run_async(service.get_contracts_similar_text(user_input))
            
            # Format the result
            if result is not None:
                formatted_result = render_template(result, command, [user_input])
                
                # Special handling for aggregation questions
                if command == "answer_aggregation_question":
                    display_text = f"""
                    ────────────────────────────────────────────────────────────
                    Question: {user_input}
                    ────────────────────────────────────────────────────────────
                    {formatted_result}
                    ────────────────────────────────────────────────────────────
                    """
                else:
                    display_text = formatted_result
                
                # Add assistant message to chat history
                st.session_state.messages.append({"role": "assistant", "content": display_text})
                st.chat_message("assistant").write(display_text)
            else:
                # Handle no results
                st.session_state.messages.append({"role": "assistant", "content": "No results found."})
                st.chat_message("assistant").write("No results found.")
                
        except Exception as e:
            error_message = f"Error: {str(e)}"
            st.session_state.messages.append({"role": "assistant", "content": error_message})
            st.chat_message("assistant").write(error_message)
            st.error(error_message)

# Display info about the system
with st.sidebar.expander("About GraphRAG Contract Review"):
    st.markdown("""
    **GraphRAG Contract Review** is a system that uses graph-based retrieval augmented generation to analyze and extract insights from contracts.
    
    The system:
    - Extracts contract data into a Neo4j graph database
    - Enables semantic search across contract text
    - Supports aggregation and insights through natural language queries
    - Provides structured access to contract information
    
    For more information, see the project documentation.
    """)

# Footer at the absolute bottom of the page
st.markdown(
    """
    <style>
    .footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: white;
        text-align: left;
        padding: 10px;
        border-top: 1px solid #ddd;
    }
    </style>
    <div class="footer">GraphRAG Contract Review System © 2025</div>
    """,
    unsafe_allow_html=True
)
