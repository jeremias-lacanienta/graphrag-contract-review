"""
Optimized Contract Service for handling tens of thousands of contracts efficiently.
Designed to support complex multi-node traversal queries without loading all data into memory.

NOTE: Run 'python initialize_optimizations.py' once before using this service
      to ensure optimal database performance.
"""
from neo4j import GraphDatabase
from typing import List, Dict, Any, Optional, Iterator, Tuple
import os
import time
import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum

# Suppress Neo4j notification messages
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

# Environment variables should be loaded by the application that uses this service

# Import existing schemas and dependencies
from AgreementSchema import Agreement, ClauseType, Party, ContractClause
from neo4j_graphrag.retrievers import VectorCypherRetriever, Text2CypherRetriever
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from formatters import my_vector_search_excerpt_record_formatter
from neo4j_graphrag.llm import OpenAILLM
from llm_formatter import LLMFormatter


class QueryOptimizationLevel(Enum):
    """Defines different levels of query optimization for large datasets"""
    BASIC = "basic"
    AGGREGATED = "aggregated"
    STREAMING = "streaming"
    DISTRIBUTED = "distributed"


@dataclass
class QueryResult:
    """Structured result container for optimized queries"""
    data: List[Dict[str, Any]]
    total_count: int
    execution_time: float
    optimization_level: QueryOptimizationLevel
    query_hash: Optional[str] = None


class ContractService:
    """
    High-performance contract service optimized for large-scale datasets.
    
    Key optimizations:
    - Streaming queries to avoid memory overload
    - Aggregation-first approach for complex traversals
    - Query result caching
    - Parallel execution for independent queries
    - Smart indexing recommendations
    """
    
    def __init__(self, uri: str, user: str, pwd: str, max_memory_contracts: int = 1000):
        self.driver = GraphDatabase.driver(uri, auth=(user, pwd))
        self.max_memory_contracts = max_memory_contracts
        self._openai_embedder = OpenAIEmbeddings(model="text-embedding-3-small")
        self._llm = OpenAILLM(model_name="gpt-4o", model_params={"temperature": 0})
        
        # Initialize LLM formatter for intelligent output formatting
        self._formatter = LLMFormatter()
        
        # Query cache for expensive operations
        self._query_cache: Dict[str, QueryResult] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # Performance monitoring
        self._query_stats = {}
        
        # Create recommended indexes on startup
        self._ensure_optimal_indexes()
    
    def _ensure_optimal_indexes(self):
        """Create indexes optimized for complex traversal queries"""
        recommended_indexes = [
            # Core entity indexes
            "CREATE INDEX agreement_contract_id IF NOT EXISTS FOR (a:Agreement) ON (a.contract_id)",
            "CREATE INDEX organization_name IF NOT EXISTS FOR (o:Organization) ON (o.name)",
            "CREATE INDEX clause_type IF NOT EXISTS FOR (c:ContractClause) ON (c.type)",
            "CREATE INDEX country_name IF NOT EXISTS FOR (c:Country) ON (c.name)",
            
            # Relationship-specific indexes
            "CREATE INDEX party_role IF NOT EXISTS FOR ()-[r:IS_PARTY_TO]-() ON (r.role)",
            "CREATE INDEX governing_state IF NOT EXISTS FOR ()-[r:GOVERNED_BY_LAW]-() ON (r.state)",
            "CREATE INDEX incorporation_state IF NOT EXISTS FOR ()-[r:INCORPORATED_IN]-() ON (r.state)",
            
            # Composite indexes for complex queries
            "CREATE INDEX agreement_type_date IF NOT EXISTS FOR (a:Agreement) ON (a.agreement_type, a.effective_date)",
            
            # Full-text search indexes
            "CREATE FULLTEXT INDEX excerpt_text IF NOT EXISTS FOR (e:Excerpt) ON EACH [e.text]",
            "CREATE FULLTEXT INDEX clause_search IF NOT EXISTS FOR (c:ContractClause) ON EACH [c.text, c.type]",
            "CREATE FULLTEXT INDEX organizationNameTextIndex IF NOT EXISTS FOR (o:Organization) ON EACH [o.name]",
            
            # Vector indexes for embeddings
            "CREATE VECTOR INDEX excerpt_embedding IF NOT EXISTS FOR (e:Excerpt) ON (e.embedding) OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`:'cosine'}}"
        ]
        
        for index_query in recommended_indexes:
            try:
                self.driver.execute_query(index_query)
            except Exception as e:
                print(f"Index creation warning: {e}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform a health check of the database and service"""
        try:
            # Test database connectivity
            result = self.driver.execute_query("RETURN 'connected' as status")
            
            # Get basic database statistics
            node_count_query = """
            MATCH (n) 
            RETURN count(n) as total_nodes
            """
            node_result, _, _ = self.driver.execute_query(node_count_query)
            total_nodes = node_result[0]['total_nodes'] if node_result else 0
            
            # Check for indexes
            index_query = "SHOW INDEXES YIELD name"
            index_result, _, _ = self.driver.execute_query(index_query)
            active_indexes = len(index_result) if index_result else 0
            
            return {
                'status': 'healthy',
                'total_nodes': total_nodes,
                'active_indexes': active_indexes,
                'cache_size': len(self._query_cache),
                'query_categories_tracked': len(self._query_stats)
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'total_nodes': 'unknown',
                'active_indexes': 'unknown'
            }
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for queries"""
        if not self._query_stats:
            return {
                'total_queries': 0,
                'average_execution_time': 0.0,
                'categories': {}
            }
        
        # Calculate overall statistics
        all_times = []
        category_stats = {}
        
        for category, times in self._query_stats.items():
            if times:
                category_stats[category] = {
                    'count': len(times),
                    'average_time': sum(times) / len(times),
                    'min_time': min(times),
                    'max_time': max(times)
                }
                all_times.extend(times)
        
        return {
            'total_queries': len(all_times),
            'average_execution_time': sum(all_times) / len(all_times) if all_times else 0.0,
            'categories': category_stats,
            'cache_hits': len(self._query_cache)
        }

    def close(self):
        """Clean up resources"""
        self.driver.close()
    
    # ==================== DYNAMIC QUERY OPTIMIZATION METHODS ====================
    
    def optimize_query_for_scale(self, original_query: str, estimated_result_size: int = None) -> str:
        """
        Dynamically optimize any Cypher query for large-scale datasets
        """
        optimized_query = original_query
        
        # Add LIMIT if not present and result size might be large
        if "LIMIT" not in optimized_query.upper():
            if estimated_result_size is None or estimated_result_size > 1000:
                optimized_query += " LIMIT 1000"
        
        # Optimize aggregations - prefer COLLECT over multiple RETURN statements
        if "RETURN" in optimized_query and optimized_query.count("RETURN") == 1:
            # Look for patterns that can be aggregated
            if "MATCH" in optimized_query and optimized_query.count("MATCH") > 2:
                # This is a complex multi-match query, add aggregation hints
                optimized_query = optimized_query.replace(
                    "RETURN", 
                    "WITH collect(DISTINCT {}) as aggregated_data\nRETURN aggregated_data,\n       size(aggregated_data) as total_count,\n      "
                )
        
        return optimized_query
    
    def execute_streaming_query(self, query: str, parameters: Dict = None, batch_size: int = 100) -> Iterator[Dict[str, Any]]:
        """
        Execute any query in streaming fashion for large datasets
        """
        # Add pagination to the query if not present
        if "SKIP" not in query.upper() or "LIMIT" not in query.upper():
            if "ORDER BY" in query.upper():
                # Insert SKIP/LIMIT before any trailing clauses
                query = query.replace("ORDER BY", "ORDER BY") + "\nSKIP $skip LIMIT $limit"
            else:
                query += "\nSKIP $skip LIMIT $limit"
        
        parameters = parameters or {}
        skip = 0
        
        while True:
            current_params = {**parameters, "skip": skip, "limit": batch_size}
            
            try:
                records, _, _ = self.driver.execute_query(query, current_params)
                
                if not records:
                    break
                
                for record in records:
                    yield dict(record)
                
                if len(records) < batch_size:
                    break
                    
                skip += batch_size
                
            except Exception as e:
                print(f"Streaming query error at skip={skip}: {e}")
                break
    
    def estimate_query_complexity(self, query: str) -> Dict[str, Any]:
        """
        Analyze query complexity to choose optimal execution strategy
        """
        query_upper = query.upper()
        
        complexity_score = 0
        complexity_factors = {}
        
        # Count different types of operations
        match_count = query_upper.count("MATCH")
        optional_match_count = query_upper.count("OPTIONAL MATCH")
        with_count = query_upper.count("WITH")
        collect_count = query_upper.count("COLLECT")
        unwind_count = query_upper.count("UNWIND")
        
        complexity_factors["match_operations"] = match_count
        complexity_factors["optional_matches"] = optional_match_count
        complexity_factors["with_clauses"] = with_count
        complexity_factors["collections"] = collect_count
        complexity_factors["unwinds"] = unwind_count
        
        # Calculate complexity score
        complexity_score += match_count * 2
        complexity_score += optional_match_count * 3  # Optional matches are more expensive
        complexity_score += with_count * 1
        complexity_score += collect_count * 2
        complexity_score += unwind_count * 4  # Unwinds can be very expensive
        
        # Check for potentially expensive patterns
        if "EXISTS {" in query:
            complexity_score += 5
            complexity_factors["exists_subqueries"] = query.count("EXISTS {")
        
        if any(keyword in query_upper for keyword in ["ALL(", "ANY(", "NONE(", "SINGLE("]):
            complexity_score += 3
            complexity_factors["list_predicates"] = True
        
        # Determine recommended strategy
        if complexity_score <= 5:
            strategy = QueryOptimizationLevel.BASIC
        elif complexity_score <= 15:
            strategy = QueryOptimizationLevel.AGGREGATED
        elif complexity_score <= 30:
            strategy = QueryOptimizationLevel.STREAMING
        else:
            strategy = QueryOptimizationLevel.DISTRIBUTED
        
        return {
            "complexity_score": complexity_score,
            "factors": complexity_factors,
            "recommended_strategy": strategy
        }
    
    # ==================== AGGREGATION AND ANALYTICS METHODS ====================
    
    def get_contract_statistics(self) -> Dict[str, Any]:
        """Get high-level statistics without loading all contracts"""
        stats_query = """
        // Contract counts and types
        MATCH (a:Agreement)
        WITH count(a) as total_contracts,
             collect(DISTINCT a.agreement_type) as contract_types
        
        // Organization statistics
        MATCH (o:Organization)
        WITH total_contracts, contract_types, count(o) as total_organizations
        
        // Clause statistics  
        MATCH (cl:ContractClause)-[:HAS_TYPE]->(ct:ClauseType)
        WITH total_contracts, contract_types, total_organizations,
             count(cl) as total_clauses,
             count(DISTINCT ct.name) as unique_clause_types
        
        // Jurisdiction distribution
        MATCH (c:Country)
        WITH total_contracts, contract_types, total_organizations, 
             total_clauses, unique_clause_types, count(c) as total_countries
        
        RETURN total_contracts, contract_types, total_organizations,
               total_clauses, unique_clause_types, total_countries
        """
        
        records, _, _ = self.driver.execute_query(stats_query)
        return dict(records[0]) if records else {}
    
    def get_top_organizations_by_contract_count(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get organizations with most contracts without loading all data"""
        query = """
        MATCH (o:Organization)-[:IS_PARTY_TO]->(a:Agreement)
        WITH o.name as organization, count(DISTINCT a) as contract_count,
             collect(DISTINCT a.agreement_type) as contract_types
        ORDER BY contract_count DESC
        LIMIT $limit
        RETURN organization, contract_count, contract_types
        """
        
        records, _, _ = self.driver.execute_query(query, parameters={"limit": limit})
        return [dict(record) for record in records]
    
    def analyze_clause_co_occurrence(self, min_frequency: int = 2) -> List[Dict[str, Any]]:
        """Analyze which clause types frequently appear together"""
        query = """
        MATCH (a:Agreement)-[:HAS_CLAUSE]->(cl:ContractClause)-[:HAS_TYPE]->(ct:ClauseType)
        WITH a, collect(DISTINCT ct.name) as clause_types
        WHERE size(clause_types) >= 2
        
        UNWIND clause_types as ct1
        UNWIND clause_types as ct2
        WHERE ct1 < ct2  // Avoid duplicates and self-pairs
        
        WITH ct1, ct2, count(*) as co_occurrence_count
        WHERE co_occurrence_count >= $min_frequency
        ORDER BY co_occurrence_count DESC
        
        RETURN ct1 as clause_type_1, ct2 as clause_type_2, co_occurrence_count
        """
        
        records, _, _ = self.driver.execute_query(
            query, 
            parameters={"min_frequency": min_frequency}
        )
        return [dict(record) for record in records]
    
    # ==================== ENHANCED SEARCH AND RETRIEVAL ====================
    
    async def answer_complex_aggregation_question(self, user_question: str) -> str:
        """
        Dynamically handle any complex question with intelligent optimization
        """
        # First try immediate pattern-based approach for better results
        pattern_result = await self._try_pattern_based_approach(user_question)
        if pattern_result and pattern_result != "No results found for the given query.":
            return pattern_result
        
        try:
            # Enhanced Neo4j schema with optimization hints
            NEO4J_SCHEMA = """
                Node properties:
                Agreement {agreement_type: STRING, contract_id: INTEGER, effective_date: STRING, 
                          renewal_term: STRING, name: STRING}
                ContractClause {type: STRING, text: STRING}
                ClauseType {name: STRING}
                Country {name: STRING}
                Excerpt {text: STRING}
                Organization {name: STRING}

                Relationship properties:
                IS_PARTY_TO {role: STRING}
                GOVERNED_BY_LAW {state: STRING}
                HAS_CLAUSE {type: STRING}
                INCORPORATED_IN {state: STRING}

                The relationships:
                (:Agreement)-[:HAS_CLAUSE]->(:ContractClause)
                (:ContractClause)-[:HAS_EXCERPT]->(:Excerpt)
                (:ContractClause)-[:HAS_TYPE]->(:ClauseType)
                (:Agreement)-[:GOVERNED_BY_LAW]->(:Country)
                (:Organization)-[:IS_PARTY_TO]->(:Agreement)
                (:Organization)-[:INCORPORATED_IN]->(:Country)
                
                Performance Notes for Large Datasets:
                - Always use LIMIT clauses (suggest LIMIT 1000 for complex queries)
                - Prefer aggregation functions (count, collect) over returning large node sets
                - Use EXISTS {} for complex filtering instead of large JOINs
                - Use WITH clauses to pipeline complex queries and reduce memory usage
                - For very complex multi-node traversals, consider using multiple smaller queries
                - Use DISTINCT in COLLECT to avoid duplicates
                - Add ORDER BY before LIMIT for consistent results
            """
            
            # Initialize enhanced retriever
            text2cypher_retriever = Text2CypherRetriever(
                llm=self._llm,
                driver=self.driver,
                neo4j_schema=NEO4J_SCHEMA
            )
            
            # Execute the query with performance monitoring
            start_time = time.time()
            result = text2cypher_retriever.search(query_text=user_question)
            execution_time = time.time() - start_time
            
            # Log performance for monitoring
            self._query_stats[user_question[:50]] = {
                'execution_time': execution_time,
                'timestamp': time.time()
            }
            
            # Process results efficiently
            if hasattr(result, 'items') and result.items:
                return await self._format_aggregation_result(result.items, user_question, execution_time)
            
            # If Text2Cypher didn't work, fall back to pattern-based approach
            return await self._fallback_query_approach(user_question)
            
        except Exception as e:
            print(f"Error in complex aggregation question: {str(e)}")
            
            # Fallback to optimized direct query approach
            return await self._fallback_query_approach(user_question)
    
    async def _fallback_query_approach(self, user_question: str) -> str:
        """
        Fallback approach when Text2Cypher fails - use pattern matching and direct queries
        """
        try:
            question_lower = user_question.lower()
            
            # Pattern-based query generation for common question types
            if any(keyword in question_lower for keyword in ['incorporation', 'incorporated', 'state']):
                return await self._handle_incorporation_questions(user_question)
            
            elif any(keyword in question_lower for keyword in ['clause', 'clauses', 'type', 'types']):
                return await self._handle_clause_questions(user_question)
            
            elif any(keyword in question_lower for keyword in ['organization', 'party', 'parties', 'company']):
                return await self._handle_organization_questions(user_question)
            
            elif any(keyword in question_lower for keyword in ['agreement', 'contract', 'contracts']):
                return await self._handle_agreement_questions(user_question)
            
            elif any(keyword in question_lower for keyword in ['jurisdiction', 'governing', 'law']):
                return await self._handle_jurisdiction_questions(user_question)
            
            elif any(keyword in question_lower for keyword in ['excerpt', 'text', 'content']):
                return await self._handle_excerpt_questions(user_question)
            
            else:
                # Generic approach - try to extract entities and build query
                return await self._handle_generic_questions(user_question)
                
        except Exception as e:
            return f"Sorry, I couldn't process that question. Error: {str(e)}"
    
    async def _try_pattern_based_approach(self, user_question: str) -> str:
        """
        Try pattern-based approach first for better accuracy on complex questions
        """
        try:
            question_lower = user_question.lower()
            
            # Enhanced pattern matching for complex questions
            if any(keyword in question_lower for keyword in ['incorporation', 'incorporated']) and \
               any(keyword in question_lower for keyword in ['delaware', 'new york', 'california', 'nevada']):
                
                # This is specifically about incorporation states - handle directly
                if any(clause_keyword in question_lower for clause_keyword in ['clause', 'license', 'assignment']):
                    return await self._handle_incorporation_with_clauses(user_question)
            
            elif any(keyword in question_lower for keyword in ['clause', 'clauses']) and \
                 ('and' in question_lower or 'both' in question_lower):
                # Questions asking for multiple clause types
                return await self._handle_multiple_clause_questions(user_question)
            
            # Try other enhanced pattern handlers
            elif any(keyword in question_lower for keyword in ['organization', 'party', 'parties']) and \
                 any(keyword in question_lower for keyword in ['incorporation', 'incorporated']):
                return await self._handle_incorporation_questions(user_question)
                
            return None  # No pattern matched, let other methods handle it
            
        except Exception as e:
            print(f"Pattern-based approach error: {e}")
            return None

    async def _handle_incorporation_with_clauses(self, question: str) -> str:
        """Enhanced handler for incorporation + clause questions"""
        question_lower = question.lower()
        
        # Extract state/country from question
        states = []
        if 'delaware' in question_lower:
            states.append('Delaware')
        if 'new york' in question_lower:
            states.append('New York')
        if 'california' in question_lower:
            states.append('California')
        if 'nevada' in question_lower:
            states.append('Nevada')
        
        # Extract clause types from question
        clause_filters = []
        if 'license' in question_lower or 'licensing' in question_lower:
            clause_filters.extend(["cl.type CONTAINS 'License'", "cl.type CONTAINS 'license'"])
        if 'assignment' in question_lower:
            clause_filters.extend(["cl.type CONTAINS 'Assignment'", "cl.type CONTAINS 'assignment'"])
        if 'liability' in question_lower:
            clause_filters.append("cl.type CONTAINS 'Liability'")
        if 'termination' in question_lower:
            clause_filters.append("cl.type CONTAINS 'Termination'")
        
        # Build the query dynamically
        where_conditions = []
        
        if states:
            state_conditions = [f"inc.state = '{state}'" for state in states]
            where_conditions.append(f"({' OR '.join(state_conditions)})")
        
        if clause_filters:
            where_conditions.append(f"({' OR '.join(clause_filters)})")
        
        where_clause = ""
        if where_conditions:
            where_clause = f"WHERE {' AND '.join(where_conditions)}"
        
        query = f"""
        MATCH (o:Organization)-[inc:INCORPORATED_IN]->(c:Country)
        MATCH (o)-[:IS_PARTY_TO]->(a:Agreement)
        MATCH (a)-[:HAS_CLAUSE]->(cl:ContractClause)
        {where_clause}
        
        WITH o, c, inc, a, collect(DISTINCT cl.type) as clause_types
        WHERE size(clause_types) >= 1
        
        RETURN o.name as organization,
               c.name as incorporation_country,
               inc.state as incorporation_state,
               a.name as agreement,
               clause_types
        ORDER BY organization
        LIMIT 50
        """
        
        try:
            records, _, _ = self.driver.execute_query(query)
            
            if not records:
                return "No organizations found matching the specified criteria."
            
            # Check if question asks for organizations with BOTH license AND assignment
            if 'both' in question_lower and 'license' in question_lower and 'assignment' in question_lower:
                # Filter for organizations that have both types
                filtered_records = []
                for record in records:
                    clause_types = record.get('clause_types', [])
                    has_license = any('license' in ct.lower() for ct in clause_types)
                    has_assignment = any('assignment' in ct.lower() for ct in clause_types)
                    if has_license and has_assignment:
                        filtered_records.append(record)
                records = filtered_records
            
            if not records:
                return await self._format_empty_response(question)
            
            # Convert records to dict format for LLM formatting
            raw_data = [dict(record) for record in records]
            
            # Use LLM formatter for professional output
            formatted_result = await self._formatter.format_contract_results(
                raw_data, question, "incorporation_clauses"
            )
            
            return formatted_result.get("formatted_response", "No results available.")
            
        except Exception as e:
            print(f"Error in incorporation with clauses query: {e}")
            return f"Error processing the query: {str(e)}"

    async def _handle_multiple_clause_questions(self, question: str) -> str:
        """Handle questions asking for multiple specific clause types"""
        question_lower = question.lower()
        
        # Extract clause types mentioned
        mentioned_clauses = []
        if 'license' in question_lower:
            mentioned_clauses.append('License')
        if 'assignment' in question_lower:
            mentioned_clauses.append('Assignment')
        if 'liability' in question_lower:
            mentioned_clauses.append('Liability')
        if 'termination' in question_lower:
            mentioned_clauses.append('Termination')
        if 'competitive' in question_lower or 'competition' in question_lower:
            mentioned_clauses.append('Compet')
            
        if len(mentioned_clauses) < 2:
            return None  # Not a multi-clause question
            
        # Build query to find agreements with multiple clause types
        clause_conditions = []
        for clause in mentioned_clauses:
            clause_conditions.append(f"cl.type CONTAINS '{clause}'")
            
        query = f"""
        MATCH (a:Agreement)-[:HAS_CLAUSE]->(cl:ContractClause)
        WHERE {' OR '.join(clause_conditions)}
        
        WITH a, collect(DISTINCT cl.type) as found_clause_types
        WHERE size(found_clause_types) >= 2
        
        MATCH (o:Organization)-[:IS_PARTY_TO]->(a)
        OPTIONAL MATCH (o)-[inc:INCORPORATED_IN]->(c:Country)
        
        RETURN a.name as agreement,
               found_clause_types,
               collect(DISTINCT {{name: o.name, country: c.name, state: inc.state}}) as parties
        ORDER BY size(found_clause_types) DESC
        LIMIT 20
        """
        
        try:
            records, _, _ = self.driver.execute_query(query)
            
            if not records:
                return await self._format_empty_response(f"No agreements found containing multiple clause types from: {', '.join(mentioned_clauses)}")
            
            # Convert records to dict format for LLM formatting
            raw_data = [dict(record) for record in records]
            
            # Use LLM formatter for professional output
            formatted_result = await self._formatter.format_contract_results(
                raw_data, question, "multiple_clauses"
            )
            
            return formatted_result.get("formatted_response", "No results available.")
            
        except Exception as e:
            print(f"Error in multiple clause query: {e}")
            return f"Error processing the query: {str(e)}"

    async def _handle_incorporation_questions(self, question: str) -> str:
        """Handle questions about incorporation states/countries"""
        query = """
        MATCH (o:Organization)-[inc:INCORPORATED_IN]->(country:Country)
        OPTIONAL MATCH (o)-[:IS_PARTY_TO]->(a:Agreement)
        
        RETURN o.name as organization,
               country.name as incorporation_country,
               inc.state as incorporation_state,
               collect(DISTINCT a.name) as agreements,
               count(DISTINCT a) as agreement_count
        ORDER BY organization
        LIMIT 100
        """
        
        records, _, _ = self.driver.execute_query(query)
        
        if not records:
            return await self._format_empty_response("No incorporation information found.")
        
        # Convert records to dict format for LLM formatting
        raw_data = [dict(record) for record in records]
        
        # Use LLM formatter for professional output
        formatted_result = await self._formatter.format_contract_results(
            raw_data, question, "incorporation"
        )
        
        return formatted_result.get("formatted_response", "No results available.")
    
    async def _handle_clause_questions(self, question: str) -> str:
        """Handle questions about clauses and clause types"""
        question_lower = question.lower()
        
        # Check if question is asking about specific clause types
        clause_filters = []
        if 'license' in question_lower or 'licensing' in question_lower:
            clause_filters.append("cl.type CONTAINS 'License'")
        if 'liability' in question_lower:
            clause_filters.append("cl.type CONTAINS 'Liability'")
        if 'termination' in question_lower:
            clause_filters.append("cl.type CONTAINS 'Termination'")
        if 'assignment' in question_lower:
            clause_filters.append("cl.type CONTAINS 'Assignment'")
        if 'competitive' in question_lower or 'competition' in question_lower:
            clause_filters.append("cl.type CONTAINS 'Compet'")
        
        where_clause = ""
        if clause_filters:
            where_clause = f"WHERE {' OR '.join(clause_filters)}"
        
        query = f"""
        MATCH (a:Agreement)-[:HAS_CLAUSE]->(cl:ContractClause)
        {where_clause}
        
        RETURN cl.type as clause_type,
               count(DISTINCT cl) as clause_count,
               count(DISTINCT a) as agreement_count,
               collect(DISTINCT a.name) as agreements
        ORDER BY clause_count DESC
        LIMIT 50
        """
        
        records, _, _ = self.driver.execute_query(query)
        
        if not records:
            return await self._format_empty_response("No clause information found matching your query.")
        
        # Convert records to dict format for LLM formatting
        raw_data = [dict(record) for record in records]
        
        # Use LLM formatter for professional output
        formatted_result = await self._formatter.format_contract_results(
            raw_data, question, "clause_analysis"
        )
        
        return formatted_result.get("formatted_response", "No results available.")
    
    async def _handle_organization_questions(self, question: str) -> str:
        """Handle questions about organizations and parties"""
        query = """
        MATCH (o:Organization)-[ipt:IS_PARTY_TO]->(a:Agreement)
        OPTIONAL MATCH (o)-[inc:INCORPORATED_IN]->(country:Country)
        
        WITH o, 
             collect(DISTINCT ipt.role) as roles,
             collect(DISTINCT a.name) as agreements,
             country.name as inc_country,
             inc.state as inc_state,
             count(DISTINCT a) as agreement_count
        
        RETURN o.name as organization,
               roles,
               agreement_count,
               agreements,
               inc_country,
               inc_state
        ORDER BY agreement_count DESC, organization
        LIMIT 50
        """
        
        records, _, _ = self.driver.execute_query(query)
        
        if not records:
            return await self._format_empty_response("No organization information found.")
        
        # Convert records to dict format for LLM formatting
        raw_data = [dict(record) for record in records]
        
        # Use LLM formatter for professional output
        formatted_result = await self._formatter.format_contract_results(
            raw_data, question, "organization_analysis"
        )
        
        return formatted_result.get("formatted_response", "No results available.")

    async def _handle_agreement_questions(self, question: str) -> str:
        """Handle questions about agreements and contracts"""
        query = """
        MATCH (a:Agreement)
        OPTIONAL MATCH (o:Organization)-[ipt:IS_PARTY_TO]->(a)
        OPTIONAL MATCH (a)-[gbl:GOVERNED_BY_LAW]->(country:Country)
        OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(cl:ContractClause)
        
        RETURN a.name as agreement_name,
               a.contract_id as contract_id,
               a.agreement_type as agreement_type,
               a.effective_date as effective_date,
               collect(DISTINCT {name: o.name, role: ipt.role}) as parties,
               country.name as governing_country,
               gbl.state as governing_state,
               count(DISTINCT cl.type) as clause_complexity,
               collect(DISTINCT cl.type) as clause_types
        ORDER BY clause_complexity DESC, agreement_name
        LIMIT 50
        """
        
        records, _, _ = self.driver.execute_query(query)
        
        if not records:
            return await self._format_empty_response("No agreement information found.")
        
        # Convert records to dict format for LLM formatting
        raw_data = [dict(record) for record in records]
        
        # Use LLM formatter for professional output
        formatted_result = await self._formatter.format_contract_results(
            raw_data, question, "agreement_analysis"
        )
        
        return formatted_result.get("formatted_response", "No results available.")

    async def _handle_jurisdiction_questions(self, question: str) -> str:
        """Handle questions about jurisdictions and governing law"""
        query = """
        MATCH (a:Agreement)-[gbl:GOVERNED_BY_LAW]->(country:Country)
        OPTIONAL MATCH (o:Organization)-[:IS_PARTY_TO]->(a)
        OPTIONAL MATCH (o)-[inc:INCORPORATED_IN]->(inc_country:Country)
        
        WITH country.name as governing_country,
             gbl.state as governing_state,
             collect(DISTINCT a.name) as agreements,
             collect(DISTINCT {
                 party: o.name,
                 inc_country: inc_country.name,
                 inc_state: inc.state
             }) as parties
        
        RETURN governing_country,
               governing_state,
               size(agreements) as agreement_count,
               agreements,
               parties
        ORDER BY agreement_count DESC
        LIMIT 20
        """
        
        records, _, _ = self.driver.execute_query(query)
        
        if not records:
            return await self._format_empty_response("No jurisdiction information found.")
        
        # Convert records to dict format for LLM formatting
        raw_data = [dict(record) for record in records]
        
        # Use LLM formatter for professional output
        formatted_result = await self._formatter.format_contract_results(
            raw_data, question, "jurisdiction_analysis"
        )
        
        return formatted_result.get("formatted_response", "No results available.")

    async def _handle_excerpt_questions(self, question: str) -> str:
        """Handle questions about contract excerpts and text content"""
        query = """
        MATCH (a:Agreement)-[:HAS_CLAUSE]->(cl:ContractClause)-[:HAS_EXCERPT]->(e:Excerpt)
        OPTIONAL MATCH (o:Organization)-[:IS_PARTY_TO]->(a)
        
        RETURN a.name as agreement_name,
               a.contract_id as contract_id,
               cl.type as clause_type,
               e.text as excerpt_text,
               collect(DISTINCT o.name) as parties
        ORDER BY agreement_name, clause_type
        LIMIT 50
        """
        
        records, _, _ = self.driver.execute_query(query)
        
        if not records:
            return await self._format_empty_response("No excerpt information found.")
        
        # Convert records to dict format for LLM formatting
        raw_data = [dict(record) for record in records]
        
        # Use LLM formatter for professional output
        formatted_result = await self._formatter.format_contract_results(
            raw_data, question, "excerpt_analysis"
        )
        
        return formatted_result.get("formatted_response", "No results available.")

    async def _handle_generic_questions(self, question: str) -> str:
        """Handle generic questions by providing database overview"""
        stats = self.get_contract_statistics()
        
        # Convert stats to structured format for LLM formatting
        raw_data = [stats]
        
        # Use LLM formatter for professional output
        formatted_result = await self._formatter.format_contract_results(
            raw_data, question, "database_overview"
        )
        
        return formatted_result.get("formatted_response", "Database information unavailable.")

    # ==================== PERFORMANCE MONITORING ====================
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for query optimization"""
        if not self._query_stats:
            return {"message": "No query statistics available"}
        
        total_queries = len(self._query_stats)
        avg_time = sum(stat['execution_time'] for stat in self._query_stats.values()) / total_queries
        
        return {
            "total_queries": total_queries,
            "average_execution_time": avg_time,
            "slowest_queries": sorted(
                [(query, stats['execution_time']) for query, stats in self._query_stats.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5]
        }
    
    def clear_performance_stats(self):
        """Clear performance statistics"""
        self._query_stats.clear()
    
    # ==================== RESULT FORMATTING ====================
    
    async def _format_aggregation_result(self, items: List[Any], question: str, execution_time: float = 0) -> str:
        """Format aggregation results using LLM for better presentation"""
        if not items:
            return await self._format_empty_response("No results found.")
        
        # Convert items to dict format for LLM processing
        raw_data = []
        for item in items[:50]:  # Limit to prevent token overflow
            if hasattr(item, '_properties'):
                raw_data.append(dict(item._properties))
            elif isinstance(item, dict):
                raw_data.append(item)
            else:
                # Convert record objects to dict representation
                try:
                    raw_data.append(dict(item))
                except:
                    raw_data.append({"result": str(item)})
        
        # Add metadata about the query
        metadata = {
            "total_results": len(items),
            "execution_time": execution_time,
            "is_large_dataset": len(items) > 100
        }
        raw_data.append({"query_metadata": metadata})
        
        # Use LLM formatter for professional output
        formatted_result = await self._formatter.format_aggregation_results(raw_data, question)
        
        return formatted_result.get("formatted_response", "No results available.")
    
    # ==================== UTILITY METHODS ====================
    
    def health_check(self) -> Dict[str, Any]:
        """Verify database connectivity and basic functionality"""
        try:
            # Test basic connectivity
            records, _, _ = self.driver.execute_query("MATCH (n) RETURN count(n) as total_nodes LIMIT 1")
            total_nodes = records[0]['total_nodes'] if records else 0
            
            # Test index status
            index_records, _, _ = self.driver.execute_query("SHOW INDEXES")
            active_indexes = len([r for r in index_records if r.get('state') == 'ONLINE'])
            
            return {
                "status": "healthy",
                "total_nodes": total_nodes,
                "active_indexes": active_indexes,
                "driver_status": "connected"
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# ==================== BACKWARD COMPATIBILITY CLASS ====================

class ContractSearchService(ContractService):
    """
    Backward-compatible wrapper for the ContractService.
    
    This ensures existing code that uses ContractSearchService continues to work
    while gaining the benefits of the optimized implementation.
    
    Usage: Replace ContractSearchService imports with this file, and everything
    should work exactly the same but with better performance.
    """
    
    def __init__(self, uri: str, user: str, pwd: str):
        """Initialize with same signature as original ContractSearchService"""
        super().__init__(uri, user, pwd)

    # ==================== BACKWARD COMPATIBILITY METHODS ====================
    
    async def get_contract(self, contract_id: int) -> Agreement:
        """Get contract by ID - maintains backward compatibility"""
        GET_CONTRACT_BY_ID_QUERY = """
            MATCH (a:Agreement {contract_id: $contract_id})-[:HAS_CLAUSE]->(clause:ContractClause)
            WITH a, collect(clause) as clauses
            MATCH (country:Country)-[i:INCORPORATED_IN]-(p:Organization)-[r:IS_PARTY_TO]-(a)
            WITH a, clauses, collect(p) as parties, collect(country) as countries, collect(r) as roles, collect(i) as states
            RETURN a as agreement, clauses, parties, countries, roles, states
        """
        
        records, _, _ = self.driver.execute_query(GET_CONTRACT_BY_ID_QUERY, {'contract_id': contract_id})
        
        if not records:
            return {}
        
        agreement_node = records[0].get('agreement')
        party_list = records[0].get('parties')
        role_list = records[0].get('roles')
        country_list = records[0].get('countries')
        state_list = records[0].get('states')
        clause_list = records[0].get('clauses')
        
        return await self._get_agreement(
            agreement_node, format="long",
            party_list=party_list, role_list=role_list,
            country_list=country_list, state_list=state_list,
            clause_list=clause_list
        )
    
    async def get_contracts(self, organization_name: str) -> List[Agreement]:
        """Get contracts by organization - maintains backward compatibility"""
        GET_CONTRACTS_BY_PARTY_NAME = """
            CALL db.index.fulltext.queryNodes('organizationNameTextIndex', $organization_name)
            YIELD node AS o, score
            WITH o, score
            ORDER BY score DESC
            LIMIT 1
            WITH o
            MATCH (o)-[:IS_PARTY_TO]->(a:Agreement)
            WITH a
            MATCH (country:Country)-[i:INCORPORATED_IN]-(p:Organization)-[r:IS_PARTY_TO]-(a:Agreement)
            RETURN a as agreement, collect(p) as parties, collect(r) as roles, collect(country) as countries, collect(i) as states
        """
        
        records, _, _ = self.driver.execute_query(GET_CONTRACTS_BY_PARTY_NAME, {'organization_name': organization_name})
        
        all_agreements = []
        for row in records:
            agreement_node = row['agreement']
            party_list = row['parties']
            role_list = row['roles']
            country_list = row['countries']
            state_list = row['states']
            
            agreement = await self._get_agreement(
                format="short",
                agreement_node=agreement_node,
                party_list=party_list,
                role_list=role_list,
                country_list=country_list,
                state_list=state_list
            )
            all_agreements.append(agreement)
        
        return all_agreements
    
    async def get_contracts_with_clause_type(self, clause_type: ClauseType) -> List[Agreement]:
        """Get contracts with specific clause type - maintains backward compatibility"""
        GET_CONTRACT_WITH_CLAUSE_TYPE_QUERY = """
            MATCH (a:Agreement)-[:HAS_CLAUSE]->(cc:ContractClause {type: $clause_type})
            WITH a
            MATCH (country:Country)-[i:INCORPORATED_IN]-(p:Organization)-[r:IS_PARTY_TO]-(a:Agreement)
            RETURN a as agreement, collect(p) as parties, collect(r) as roles, collect(country) as countries, collect(i) as states
        """
        
        clause_type_value = str(clause_type.value) if hasattr(clause_type, 'value') else str(clause_type)
        
        records, _, _ = self.driver.execute_query(GET_CONTRACT_WITH_CLAUSE_TYPE_QUERY, {'clause_type': clause_type_value})
        
        all_agreements = []
        for row in records:
            agreement_node = row['agreement']
            party_list = row['parties']
            role_list = row['roles']
            country_list = row['countries']
            state_list = row['states']
            
            agreement = await self._get_agreement(
                format="short",
                agreement_node=agreement_node,
                party_list=party_list,
                role_list=role_list,
                country_list=country_list,
                state_list=state_list
            )
            all_agreements.append(agreement)
        
        return all_agreements
    
    async def get_contracts_without_clause(self, clause_type: ClauseType) -> List[Agreement]:
        """Get contracts without specific clause type - maintains backward compatibility"""
        GET_CONTRACT_WITHOUT_CLAUSE_TYPE_QUERY = """
            MATCH (a:Agreement)
            OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(cc:ContractClause {type: $clause_type})
            WITH a,cc
            WHERE cc is NULL
            WITH a
            MATCH (country:Country)-[i:INCORPORATED_IN]-(p:Organization)-[r:IS_PARTY_TO]-(a)
            RETURN a as agreement, collect(p) as parties, collect(r) as roles, collect(country) as countries, collect(i) as states
        """
        
        clause_type_value = str(clause_type.value) if hasattr(clause_type, 'value') else str(clause_type)
        
        records, _, _ = self.driver.execute_query(GET_CONTRACT_WITHOUT_CLAUSE_TYPE_QUERY, {'clause_type': clause_type_value})
        
        all_agreements = []
        for row in records:
            agreement_node = row['agreement']
            party_list = row['parties']
            role_list = row['roles']
            country_list = row['countries']
            state_list = row['states']
            
            agreement = await self._get_agreement(
                format="short",
                agreement_node=agreement_node,
                party_list=party_list,
                role_list=role_list,
                country_list=country_list,
                state_list=state_list
            )
            all_agreements.append(agreement)
        
        return all_agreements
    
    async def get_contracts_similar_text(self, clause_text: str) -> List[Agreement]:
        """Get contracts with similar text - maintains backward compatibility"""
        EXCERPT_TO_AGREEMENT_TRAVERSAL_QUERY = """
            MATCH (a:Agreement)-[:HAS_CLAUSE]->(cc:ContractClause)-[:HAS_EXCERPT]-(node) 
            RETURN a.name as agreement_name, a.contract_id as contract_id, cc.type as clause_type, node.text as excerpt
        """
        
        retriever = VectorCypherRetriever(
            driver=self.driver,
            index_name="excerpt_embedding",
            embedder=self._openai_embedder,
            retrieval_query=EXCERPT_TO_AGREEMENT_TRAVERSAL_QUERY,
            result_formatter=my_vector_search_excerpt_record_formatter
        )
        
        retriever_result = retriever.search(query_text=clause_text, top_k=3)
        
        agreements = []
        for item in retriever_result.items:
            content = item.content
            agreement = {
                'name': content['agreement_name'],
                'contract_id': content['contract_id']
            }
            clause = {
                "type": content['clause_type'],
                "excerpts": [content['excerpt']]
            }
            agreement['clauses'] = [clause]
            agreements.append(agreement)
        
        return agreements
    
    async def answer_aggregation_question(self, user_question: str) -> str:
        """Main question answering method - uses new dynamic optimization"""
        return await self.answer_complex_aggregation_question(user_question)
    
    async def get_contract_excerpts(self, contract_id: int):
        """Get contract excerpts - maintains backward compatibility"""
        GET_CONTRACT_CLAUSES_QUERY = """
        MATCH (a:Agreement {contract_id: $contract_id})-[:HAS_CLAUSE]->(cc:ContractClause)-[:HAS_EXCERPT]->(e:Excerpt)
        RETURN a as agreement, cc.type as contract_clause_type, collect(e.text) as excerpts 
        """
        
        clause_records, _, _ = self.driver.execute_query(GET_CONTRACT_CLAUSES_QUERY, {'contract_id': contract_id})
        
        clause_dict = {}
        agreement_node = None
        
        for row in clause_records:
            agreement_node = row['agreement']
            clause_type = row['contract_clause_type']
            relevant_excerpts = row['excerpts']
            clause_dict[clause_type] = relevant_excerpts
        
        if agreement_node:
            return await self._get_agreement(
                format="long",
                agreement_node=agreement_node,
                clause_dict=clause_dict
            )
        
        return {}
    
    # ==================== HELPER METHODS ====================
    
    async def _get_agreement(self, agreement_node, format="short", party_list=None, role_list=None, 
                           country_list=None, state_list=None, clause_list=None, clause_dict=None):
        """Helper method to construct Agreement objects"""
        agreement = {}
        
        if format == "short" and agreement_node:
            agreement = {
                "contract_id": agreement_node.get('contract_id'),
                "name": agreement_node.get('name'),
                "agreement_type": agreement_node.get('agreement_type')
            }
            agreement['parties'] = await self._get_parties(
                party_list=party_list,
                role_list=role_list,
                country_list=country_list,
                state_list=state_list
            )
        
        elif format == "long" and agreement_node:
            agreement = {
                "contract_id": agreement_node.get('contract_id'),
                "name": agreement_node.get('name'),
                "agreement_type": agreement_node.get('agreement_type'),
                "agreement_date": agreement_node.get('agreement_date'),
                "effective_date": agreement_node.get('effective_date'),
                "expiration_date": agreement_node.get('expiration_date'),
                "renewal_term": agreement_node.get('renewal_term')
            }
            agreement['parties'] = await self._get_parties(
                party_list=party_list,
                role_list=role_list,
                country_list=country_list,
                state_list=state_list
            )
            
            clauses = []
            if clause_list:
                for clause in clause_list:
                    clause_obj = {"type": clause.get('type')}
                    clauses.append(clause_obj)
            elif clause_dict:
                for clause_type_key in clause_dict:
                    clause = {"type": clause_type_key, "excerpts": clause_dict[clause_type_key]}
                    clauses.append(clause)
            
            agreement['clauses'] = clauses
        
        return agreement
    
    async def _get_parties(self, party_list=None, role_list=None, country_list=None, state_list=None):
        """Helper method to construct Party objects"""
        parties = []
        if party_list:
            for i in range(len(party_list)):
                party = {
                    "name": party_list[i].get('name'),
                    "role": role_list[i].get('role') if role_list and i < len(role_list) else None,
                    "incorporation_country": country_list[i].get('name') if country_list and i < len(country_list) else None,
                    "incorporation_state": state_list[i].get('state') if state_list and i < len(state_list) else None
                }
                parties.append(party)
        
        return parties

    def _format_aggregation_result(self, items: List[Any], question: str, execution_time: float = 0) -> str:
        """Format aggregation results with smart truncation for large datasets"""
        if not items:
            return "No results found."
        
        # For very large result sets, provide summary statistics
        if len(items) > 100:
            return self._format_large_result_summary(items, question, execution_time)
        
        # Standard formatting for manageable result sets
        answer = f"Query results (showing {len(items)} items"
        if execution_time > 0:
            answer += f", execution time: {execution_time:.3f}s"
        answer += "):\n\n"
        
        for i, record in enumerate(items[:50]):  # Limit display to 50 items
            record_str = str(record).replace("<Record ", "").replace(">", "").strip()
            answer += f"  {i+1}. {record_str}\n"
        
        if len(items) > 50:
            answer += f"\n... and {len(items) - 50} more results (truncated for readability)"
        
        return answer
    
    def _format_large_result_summary(self, items: List[Any], question: str, execution_time: float = 0) -> str:
        """Provide summary statistics for very large result sets"""
        total_count = len(items)
        
        # Sample first few results
        sample_size = min(10, total_count)
        sample_results = items[:sample_size]
        
        summary = f"Large result set found ({total_count} total results"
        if execution_time > 0:
            summary += f", execution time: {execution_time:.3f}s"
        summary += ").\n\n"
        
        summary += f"Sample of first {sample_size} results:\n"
        
        for i, record in enumerate(sample_results):
            record_str = str(record).replace("<Record ", "").replace(">", "").strip()
            summary += f"  {i+1}. {record_str}\n"
        
        summary += f"\n... and {total_count - sample_size} more results."
        summary += f"\n\nFor the complete dataset, consider using more specific filters or aggregation queries."
        
        return summary

    # ==================== HELPER METHODS ====================
    
    async def _format_empty_response(self, message: str) -> str:
        """Helper method to format empty responses using LLM"""
        empty_result = await self._formatter._format_empty_response(message)
        return empty_result.get("formatted_response", message)
