"""
Template Renderer Module

This module provides funct    # Group by contract ID to remove duplicates
    contracts_by_id = {}
    for item in results:
        contract_id = item.get('contract_id')
        agreement_name = item.get('agreement_name', 'Unnamed Contract')
        
        if contract_id not in contracts_by_id:
            contracts_by_id[contract_id] = {
                'id': contract_id,
                'name': agreement_name,  # Use name in template
                'clauses': []
            }
        
        # Collect clause information
        for clause in item.get('clauses', []):
            clause_type = clause.get('clause_type', 'Unknown')
            excerpts = clause.get('excerpts', [])g Jinja2 templates for the GraphRAG Contract Review application.
"""

import os
import re
from typing import Any, Dict, List, Union, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Configure Jinja2 environment
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml']),
    trim_blocks=True,
    lstrip_blocks=True
)

def render_contract(contract: Dict[str, Any]) -> str:
    """
    Render a single contract using the contract template
    
    Args:
        contract: Contract data dictionary
        
    Returns:
        Formatted string representation of the contract
    """
    template = env.get_template("contract.jinja2")
    return template.render(contract=contract, title="Contract Information")

def render_contracts_list(contracts: List[Dict[str, Any]]) -> str:
    """
    Render a list of contracts using the contracts_list template
    
    Args:
        contracts: List of contract data dictionaries
        
    Returns:
        Formatted string representation of the contracts list
    """
    template = env.get_template("contracts_list.jinja2")
    return template.render(contracts=contracts, title="Contracts List")

def render_similar_text_results(results: List[Dict[str, Any]]) -> str:
    """
    Render contracts with similar text using the similar_text template
    
    Args:
        results: List of contract results with similar text
        
    Returns:
        Formatted string representation of the similar text results
    """
    # Group by contract ID to remove duplicates
    contracts_by_id = {}
    for item in results:
        contract_id = item.get('contract_id')
        agreement_name = item.get('name', 'Unnamed Contract')
        
        if contract_id not in contracts_by_id:
            contracts_by_id[contract_id] = {
                'name': agreement_name,
                'id': contract_id,
                'clauses': []
            }
        
        # Collect clause information
        for clause in item.get('clauses', []):
            clause_type = clause.get('type', 'Unknown')
            excerpts = clause.get('excerpts', [])
            
            # Check if this clause type already exists
            clause_exists = False
            for existing_clause in contracts_by_id[contract_id]['clauses']:
                if existing_clause['type'] == clause_type:
                    # Merge excerpts, avoiding duplicates
                    existing_excerpts = set(existing_clause['excerpts'])
                    existing_excerpts.update(excerpts)
                    existing_clause['excerpts'] = sorted(list(existing_excerpts))
                    clause_exists = True
                    break
                    
            if not clause_exists:
                contracts_by_id[contract_id]['clauses'].append({
                    'type': clause_type,  # Use type in template
                    'excerpts': excerpts
                })
    
    # Convert to list for template
    contracts = list(contracts_by_id.values())
    
    template = env.get_template("similar_text.jinja2")
    return template.render(contracts=contracts, title="Contracts with Similar Text")

def render_excerpts(contract: Dict[str, Any], excerpts: List[Dict[str, Any]]) -> str:
    """
    Render contract excerpts using the excerpts template
    
    Args:
        contract: Contract data dictionary
        excerpts: List of excerpt data dictionaries
        
    Returns:
        Formatted string representation of the excerpts
    """
    template = env.get_template("excerpts.jinja2")
    return template.render(contract=contract, excerpts=excerpts, title="Contract Excerpts")

def render_aggregation_question(question: str, answer: str, supporting_data: Optional[List[str]] = None) -> str:
    """
    Render aggregation question answer using the aggregation_question template
    
    Args:
        question: The question that was asked
        answer: The answer to the question
        supporting_data: Optional supporting data for the answer
        
    Returns:
        Formatted string representation of the question and answer
    """
    template = env.get_template("aggregation_question.jinja2")
    return template.render(
        question=question,
        answer=answer,
        supporting_data=supporting_data,
        title="Aggregation Question Results"
    )

def format_result(result: Any, command: str = None, args: List[str] = None) -> str:
    """
    Format query results into readable text using the appropriate template.
    
    Args:
        result: Query result from ContractService methods
        command: The command that was used (optional)
        args: The arguments to the command (optional)
        
    Returns:
        Formatted string output
    """
    # Handle empty results
    if not result:
        return "No results found."
    
    # Handle string results (already formatted or error messages)
    if isinstance(result, str):
        return result
    
    # Use command-specific templates if we know the command
    if command:
        if command == "get_contract" and isinstance(result, dict):
            return render_contract(result)
        
        elif command in ["get_contracts_by_party", "get_contracts_with_clause_type", "get_contracts_without_clause"] and isinstance(result, list):
            return render_contracts_list(result)
        
        elif command in ["get_contracts_similar_text", "search"] and isinstance(result, list):
            return render_similar_text_results(result)
        
        elif command == "get_contract_excerpts" and isinstance(result, dict) and 'contract' in result and 'excerpts' in result:
            return render_excerpts(result['contract'], result['excerpts'])
        
        elif command == "answer_aggregation_question" and args and len(args) > 0:
            question = args[0]
            answer = result
            return render_aggregation_question(question, answer)
    
    # If we can't determine the specific template, use generic formatting
    if isinstance(result, dict):
        return render_contract(result)
    elif isinstance(result, list) and result and isinstance(result[0], dict):
        if 'agreement_name' in result[0]:
            return render_contracts_list(result)
        elif 'clause_type' in result[0]:
            return render_excerpts({'agreement_name': 'Unknown'}, result)
    
    # For any other type of result, convert to string
    return str(result)
