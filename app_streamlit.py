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

# Sidebar with command options
st.sidebar.markdown("## Command Menu")
st.sidebar.markdown("Select a command to execute")

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

# Sidebar command selection
selected_command = st.sidebar.radio("Select Command", [cmd["name"] for cmd in commands])
selected_cmd = next((cmd for cmd in commands if cmd["name"] == selected_command), None)

# Display information about the selected command
st.sidebar.markdown("---")
st.sidebar.markdown(f"### {selected_cmd['name']}")
st.sidebar.markdown(f"{selected_cmd['description']}")
st.sidebar.markdown(f"**Input format**: {selected_cmd['args_description']}")
st.sidebar.markdown(f"**Example**: `{selected_cmd['example']}`")

# Command execution section
st.markdown("<h2 class='sub-header'>Execute Command</h2>", unsafe_allow_html=True)

# Chat-like input interface
for message in st.session_state.messages:
    if message["role"] == "user":
        st.chat_message("user").write(message["content"])
    else:
        st.chat_message("assistant").write(message["content"])

# Input field for command arguments
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

# Footer
st.markdown("<div class='separator'></div>", unsafe_allow_html=True)
st.markdown("GraphRAG Contract Review System © 2025", unsafe_allow_html=True)
