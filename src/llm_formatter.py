"""
LLM-based output formatting for GraphRAG Contract Review application.
Provides intelligent, context-aware formatting using LLM that directly answers user questions with grounded evidence.
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from openai import OpenAI
import os

@dataclass
class FormattingConfig:
    """Configuration for LLM formatting"""
    max_items_for_llm: int = 20
    max_tokens: int = 2000
    temperature: float = 0.1
    model: str = "gpt-4o-mini"
    include_insights: bool = True
    include_summary_stats: bool = True

class LLMFormatter:
    """
    Intelligent formatter that uses LLM to create natural, readable output
    from raw contract analysis data.
    """
    
    def __init__(self, config: Optional[FormattingConfig] = None):
        self.config = config or FormattingConfig()
        try:
            # Check if Azure OpenAI configuration is provided
            azure_endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
            azure_api_key = os.getenv('AZURE_OPENAI_API_KEY')
            azure_api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')
            azure_deployment = os.getenv('AZURE_OPENAI_DEPLOYMENT') or os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')
            
            if azure_endpoint and azure_api_key:
                # Use Azure OpenAI
                from openai import AzureOpenAI
                self.client = AzureOpenAI(
                    azure_endpoint=azure_endpoint,
                    api_key=azure_api_key,
                    api_version=azure_api_version
                )
                # Override model name with Azure deployment name if provided
                if azure_deployment:
                    self.config.model = azure_deployment
                self.client_available = True
            else:
                self.client = None
                self.client_available = False
        except Exception as e:
            print(f"Warning: LLM client initialization failed: {e}")
            print("Falling back to basic formatting without LLM enhancement")
            self.client = None
            self.client_available = False
        
    async def format_contract_results(self, raw_data: List[Dict], user_question: str, 
                                    query_type: str = "general") -> Dict[str, Any]:
        """
        Format contract query results using LLM for natural presentation
        """
        if not raw_data:
            return await self._format_empty_response(user_question)
        
        # Prepare data for LLM processing
        formatted_data = self._prepare_data_for_llm(raw_data, query_type)
        summary_stats = self._generate_summary_stats(raw_data)
        
        # Generate LLM-formatted response
        llm_response = await self._generate_llm_formatted_response(
            formatted_data, user_question, query_type, summary_stats
        )
        
        return {
            "success": True,
            "formatted_response": llm_response,
            "summary_stats": summary_stats,
            "raw_data_count": len(raw_data),
            "user_question": user_question,
            "generated_at": datetime.now().isoformat(),
            "query_type": query_type
        }
    
    async def format_aggregation_results(self, raw_data: List[Dict], user_question: str) -> Dict[str, Any]:
        """
        Format aggregation query results with emphasis on patterns and insights
        """
        return await self.format_contract_results(raw_data, user_question, "aggregation")
    
    async def format_similar_text_results(self, raw_data: List[Dict], user_question: str, 
                                        query_text: str = "") -> Dict[str, Any]:
        """
        Format similarity search results with relevance emphasis
        """
        result = await self.format_contract_results(raw_data, user_question, "similarity")
        result["query_text"] = query_text
        return result
    
    async def format_contract_list_results(self, raw_data: List[Dict], user_question: str) -> Dict[str, Any]:
        """
        Format contract listing results with organization focus
        """
        return await self.format_contract_results(raw_data, user_question, "contract_list")
    
    def _prepare_data_for_llm(self, raw_data: List[Dict], query_type: str = "general") -> str:
        """
        Convert raw data to a clean, structured format for LLM processing
        """
        if not raw_data:
            return "No data available."
        
        # Limit data size to avoid token limits
        limited_data = raw_data[:self.config.max_items_for_llm]
        
        formatted_items = []
        for i, item in enumerate(limited_data, 1):
            item_lines = [f"Result {i}:"]
            
            for key, value in item.items():
                if value is None or value == "":
                    continue
                    
                if isinstance(value, list):
                    if len(value) == 0:
                        continue
                    elif query_type == "excerpts" and key.lower() == "clauses":
                        # Special handling for excerpt clauses - show each clause separately
                        item_lines.append(f"  • {self._format_key(key)} ({len(value)} total):")
                        for i, clause in enumerate(value, 1):
                            if isinstance(clause, dict):
                                clause_type = clause.get('type', 'Unknown')
                                excerpts = clause.get('excerpts', [])
                                item_lines.append(f"    {i}. {clause_type}")
                                for j, excerpt in enumerate(excerpts, 1):
                                    item_lines.append(f"       Excerpt {j}: {excerpt}")
                            else:
                                item_lines.append(f"    {i}. {clause}")
                    elif len(value) <= 5 or query_type in ["excerpts", "contract", "contract_detail"]:
                        # For excerpts, contracts, show all items; for others, show all if <= 5
                        item_lines.append(f"  • {self._format_key(key)}: {', '.join(map(str, value))}")
                    else:
                        preview = ', '.join(map(str, value[:3]))
                        item_lines.append(f"  • {self._format_key(key)}: {preview}... ({len(value)} total)")
                elif isinstance(value, dict):
                    if value:  # Only show non-empty dicts
                        dict_summary = ', '.join([f"{k}: {v}" for k, v in list(value.items())[:3]])
                        item_lines.append(f"  • {self._format_key(key)}: {dict_summary}")
                else:
                    # Truncate very long strings
                    str_value = str(value)
                    if len(str_value) > 200:
                        str_value = str_value[:200] + "..."
                    item_lines.append(f"  • {self._format_key(key)}: {str_value}")
            
            formatted_items.append('\n'.join(item_lines))
        
        result = '\n\n'.join(formatted_items)
        
        if len(raw_data) > self.config.max_items_for_llm:
            result += f"\n\n[... and {len(raw_data) - self.config.max_items_for_llm} more results not shown]"
        
        return result
    
    def _format_key(self, key: str) -> str:
        """Format field keys to be more readable"""
        return key.replace('_', ' ').title()
    
    def _generate_summary_stats(self, raw_data: List[Dict]) -> Dict[str, Any]:
        """
        Generate summary statistics from raw data
        """
        stats = {
            "total_results": len(raw_data),
            "unique_organizations": set(),
            "unique_contract_types": set(),
            "unique_jurisdictions": set(),
            "date_range": {"earliest": None, "latest": None},
            "common_fields": {}
        }
        
        field_counts = {}
        
        for record in raw_data:
            for key, value in record.items():
                # Count field occurrences
                field_counts[key] = field_counts.get(key, 0) + 1
                
                # Collect unique values for key fields
                if 'organization' in key.lower() and value:
                    if isinstance(value, list):
                        stats["unique_organizations"].update(value)
                    else:
                        stats["unique_organizations"].add(str(value))
                
                if any(term in key.lower() for term in ['agreement', 'contract', 'type']) and value:
                    if isinstance(value, list):
                        stats["unique_contract_types"].update(value)
                    else:
                        stats["unique_contract_types"].add(str(value))
                
                if any(term in key.lower() for term in ['jurisdiction', 'state', 'country', 'law']) and value:
                    if isinstance(value, list):
                        stats["unique_jurisdictions"].update(value)
                    else:
                        stats["unique_jurisdictions"].add(str(value))
                
                # Track dates
                if any(term in key.lower() for term in ['date', 'time']) and value:
                    try:
                        # This is a simple approach - you might need more sophisticated date parsing
                        date_str = str(value)
                        if stats["date_range"]["earliest"] is None:
                            stats["date_range"]["earliest"] = date_str
                            stats["date_range"]["latest"] = date_str
                        else:
                            if date_str < stats["date_range"]["earliest"]:
                                stats["date_range"]["earliest"] = date_str
                            if date_str > stats["date_range"]["latest"]:
                                stats["date_range"]["latest"] = date_str
                    except:
                        pass
        
        # Convert sets to lists and get counts
        stats["unique_organizations"] = list(stats["unique_organizations"])
        stats["unique_contract_types"] = list(stats["unique_contract_types"])
        stats["unique_jurisdictions"] = list(stats["unique_jurisdictions"])
        stats["organization_count"] = len(stats["unique_organizations"])
        stats["contract_type_count"] = len(stats["unique_contract_types"])
        stats["jurisdiction_count"] = len(stats["unique_jurisdictions"])
        
        # Most common fields
        stats["common_fields"] = {k: v for k, v in sorted(field_counts.items(), 
                                                          key=lambda x: x[1], reverse=True)[:5]}
        
        return stats
    
    async def _generate_llm_formatted_response(self, formatted_data: str, user_question: str, 
                                             query_type: str, summary_stats: Dict) -> str:
        """
        Use LLM to generate a natural, well-formatted response
        """
        # If OpenAI client is not available, use fallback formatting
        if not self.client_available:
            return self._fallback_format_response(formatted_data, user_question, summary_stats)
            
        prompt = self._create_formatting_prompt(formatted_data, user_question, query_type, summary_stats)
        
        try:
            # Use more tokens for excerpt and contract detail queries to accommodate all data
            max_tokens = 4000 if query_type in ["excerpts", "contract_detail", "contract"] else self.config.max_tokens
            
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(query_type)},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"LLM formatting error: {e}")
            return self._fallback_format_response(formatted_data, user_question, summary_stats)
    
    def _create_formatting_prompt(self, formatted_data: str, user_question: str, 
                                query_type: str, summary_stats: Dict) -> str:
        """
        Create a comprehensive prompt for LLM formatting focused on precise answers
        """
        stats_summary = f"""
Summary Statistics:
- Total Results: {summary_stats['total_results']}
- Organizations: {summary_stats['organization_count']}
- Contract Types: {summary_stats['contract_type_count']}
- Jurisdictions: {summary_stats['jurisdiction_count']}
"""
        
        # Add specific instructions for excerpt and contract detail queries
        special_instruction = ""
        if query_type == "excerpts":
            special_instruction = """
🚨 MANDATORY REQUIREMENT FOR EXCERPTS 🚨
You MUST display ALL clause excerpts from the provided data. The data shows 10 clauses - you must display all 10 numbered clauses with their excerpts. Count the clauses in the data and ensure your response contains exactly that many clauses. Do not omit any clauses. Do not use "..." to indicate more items. Do not provide samples or examples. Show EVERY SINGLE clause type and its complete excerpt text. If you show fewer clauses than are in the data, you have failed the task.

VERIFICATION REQUIREMENT: Before you finish, count how many clauses you displayed and make sure it matches the number in the data (10 clauses).
"""
        elif query_type in ["contract_detail", "contract"]:
            special_instruction = """
🚨 MANDATORY REQUIREMENT FOR CONTRACT DETAILS 🚨
You MUST display ALL clauses from the contract data. The data shows multiple clauses - you must list every single clause type without omitting any. Do not use "..." to indicate more items. Do not summarize or truncate the clause list. Show EVERY clause type that appears in the data. Count the clauses and display exactly that many.

VERIFICATION REQUIREMENT: Before you finish, count how many clauses you displayed and make sure it matches the number in the data.
"""
        
        return f"""
User Question: "{user_question}"
Query Type: {query_type}

{stats_summary}

Raw Data to Format:
{formatted_data}
{special_instruction}
CRITICAL: You must provide a PRECISE, GROUNDED answer that directly addresses the user's specific question. Follow these requirements:

1. **Answer the exact question asked** - Don't provide general information, focus only on what was specifically requested
2. **Use specific evidence from the data** - Quote exact text, names, numbers, and details that support your answer
3. **Be factual and grounded** - Only state what can be directly verified from the provided data
4. **Cite specific contracts/sources** - Reference which contracts or organizations the information comes from
5. **If data is insufficient** - Clearly state what cannot be answered with the available information
6. **Structure for clarity** - Use headers and bullet points only when they help answer the specific question

Format Guidelines:
- Start with a direct answer to the question
- Provide supporting evidence with specific quotes and references
- Use bullet points only for multiple related findings
- Include exact numbers, dates, names from the data
- End with limitations if the data doesn't fully answer the question

Do NOT provide generic contract analysis - answer ONLY what was asked with precise evidence.
"""
    
    def _get_system_prompt(self, query_type: str) -> str:
        """
        Get appropriate system prompt based on query type
        """
        base_prompt = """You are a precise contract analyst who provides direct, factual answers to specific questions. You ONLY answer what is explicitly asked using evidence from the provided data. You never provide general information or analysis beyond what was requested."""
        
        type_specific = {
            "aggregation": " Focus on precise statistical answers and patterns that directly address the question.",
            "similarity": " Focus on relevance and explain exactly why results match the query with specific evidence.",
            "contract_list": " Focus on specific organizational details that answer the question.",
            "contract_detail": " CRITICAL REQUIREMENT: You must display ALL clauses completely. Never use '...' or '(X total)' for clauses. List every single clause name individually. This is a mandatory requirement.",
            "excerpts": " CRITICAL: Display ALL clause excerpts from the data. Do not omit any clauses or excerpts. Show every single clause type and its excerpt text without summarizing or truncating.",
            "general": " Provide only the specific information requested with supporting evidence."
        }
        
        return base_prompt + type_specific.get(query_type, type_specific["general"])
    
    async def _format_empty_response(self, user_question: str) -> Dict[str, Any]:
        """
        Generate a helpful response when no data is found
        """
        empty_prompt = f"""
The user asked: "{user_question}"

No matching data was found in the contract database.

Provide a direct response that:
- States clearly that no data was found for their specific question
- Suggests rephrasing the question or trying different search terms
- Keeps the response focused on their specific request
- Uses 2-3 sentences maximum

Be precise and helpful, not generic.
"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant for a contract analysis system."},
                    {"role": "user", "content": empty_prompt}
                ],
                max_tokens=300,
                temperature=0.1
            )
            
            formatted_response = response.choices[0].message.content
            
        except Exception as e:
            formatted_response = f"""No data found for your question: "{user_question}"

This could be because the search terms don't match available contract content, or the specific information requested isn't in the current dataset. Try rephrasing your question or using broader search terms."""
        
        return {
            "success": False,
            "formatted_response": formatted_response,
            "summary_stats": {"total_results": 0},
            "raw_data_count": 0,
            "user_question": user_question,
            "generated_at": datetime.now().isoformat(),
            "query_type": "empty_result"
        }
    
    def _fallback_format_response(self, formatted_data: str, user_question: str, 
                                summary_stats: Dict) -> str:
        """
        Fallback formatting when LLM is unavailable
        """
        return f"""**Answer to:** {user_question}

**Found:** {summary_stats['total_results']} result(s) from {summary_stats['organization_count']} organization(s)

{formatted_data}

*Note: Basic formatting used - LLM analysis unavailable*
"""

# Convenience functions for backward compatibility
async def format_result(data: Any, query_type: str, user_question: str = "", **kwargs) -> str:
    """
    Main formatting function that provides grounded, precise answers to user questions
    """
    formatter = LLMFormatter()
    
    # Handle pre-formatted aggregation results
    if query_type == "answer_aggregation_question" and isinstance(data, str) and len(data) > 50:
        # This is already a formatted result from the aggregation service, return as-is
        return data
    
    # Convert data to list of dicts if needed
    if not isinstance(data, list):
        if isinstance(data, dict):
            data = [data]
        else:
            data = []
    
    # Route to appropriate formatter based on query type
    if query_type == "aggregation_question":
        result = await formatter.format_aggregation_results(data, user_question)
    elif query_type == "similar_text":
        query_text = kwargs.get('query_text', '')
        result = await formatter.format_similar_text_results(data, user_question, query_text)
    elif query_type == "contracts_list":
        result = await formatter.format_contract_list_results(data, user_question)
    elif query_type == "contract":
        result = await formatter.format_contract_results(data, user_question, "contract_detail")
    elif query_type == "excerpts":
        result = await formatter.format_contract_results(data, user_question, "excerpts")
    else:
        result = await formatter.format_contract_results(data, user_question)
    
    return result.get("formatted_response", "No results available.")

# Create global formatter instance
_global_formatter = None

def get_formatter() -> LLMFormatter:
    """Get or create global formatter instance"""
    global _global_formatter
    if _global_formatter is None:
        _global_formatter = LLMFormatter()
    return _global_formatter
