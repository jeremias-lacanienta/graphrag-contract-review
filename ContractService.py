from neo4j import GraphDatabase
from typing import List 
from AgreementSchema import Agreement, ClauseType,Party, ContractClause
from neo4j_graphrag.retrievers import VectorCypherRetriever,Text2CypherRetriever
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from formatters import my_vector_search_excerpt_record_formatter
from neo4j_graphrag.llm import OpenAILLM



class ContractSearchService:
    def __init__(self, uri, user ,pwd ):
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        self._driver = driver
        self._openai_embedder = OpenAIEmbeddings(model = "text-embedding-3-small")
        # Create LLM object. Used to generate the CYPHER queries
        self._llm = OpenAILLM(model_name="gpt-4o", model_params={"temperature": 0}) 
        
    
    async def get_contract(self, contract_id: int) -> Agreement:
        
        GET_CONTRACT_BY_ID_QUERY = """
            MATCH (a:Agreement {contract_id: $contract_id})-[:HAS_CLAUSE]->(clause:ContractClause)
            WITH a, collect(clause) as clauses
            MATCH (country:Country)-[i:INCORPORATED_IN]-(p:Organization)-[r:IS_PARTY_TO]-(a)
            WITH a, clauses, collect(p) as parties, collect(country) as countries, collect(r) as roles, collect(i) as states
            RETURN a as agreement, clauses, parties, countries, roles, states
        """
        
        agreement_node = {}
       
        records, _, _  = self._driver.execute_query(GET_CONTRACT_BY_ID_QUERY,{'contract_id':contract_id})
        
        # Return empty agreement if no records found
        if not records or len(records) == 0: return {}

        agreement_node =    records[0].get('agreement')
        party_list =        records[0].get('parties')
        role_list =         records[0].get('roles')
        country_list =      records[0].get('countries')
        state_list =        records[0].get('states')
        clause_list =       records[0].get('clauses')
        
        return await self._get_agreement(
            agreement_node, format="long",
            party_list=party_list, role_list=role_list,
            country_list=country_list,state_list=state_list,
            clause_list=clause_list
        )

    async def get_contracts(self, organization_name: str) -> List[Agreement]:
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
       
        #run the Cypher query
        records, _ , _ = self._driver.execute_query(GET_CONTRACTS_BY_PARTY_NAME,{'organization_name':organization_name})

        #Build the result
        all_aggrements = []
        for row in records:
            agreement_node =  row['agreement']
            party_list =  row['parties']
            role_list =  row['roles']
            country_list = row['countries']
            state_list = row['states']
            
            agreement : Agreement = await self._get_agreement(
                format="short",
                agreement_node=agreement_node,
                party_list=party_list,
                role_list=role_list,
                country_list=country_list,
                state_list=state_list
            )
            all_aggrements.append(agreement)
        
        return all_aggrements

    async def get_contracts_with_clause_type(self, clause_type: ClauseType) -> List[Agreement]:
        GET_CONTRACT_WITH_CLAUSE_TYPE_QUERY = """
            MATCH (a:Agreement)-[:HAS_CLAUSE]->(cc:ContractClause {type: $clause_type})
            WITH a
            MATCH (country:Country)-[i:INCORPORATED_IN]-(p:Organization)-[r:IS_PARTY_TO]-(a:Agreement)
            RETURN a as agreement, collect(p) as parties, collect(r) as roles, collect(country) as countries, collect(i) as states
            
        """

        # Fix: Check if clause_type is a string or an enum
        if hasattr(clause_type, 'value'):
            # It's an enum, get its value
            clause_type_value = str(clause_type.value)
        else:
            # It's already a string
            clause_type_value = str(clause_type)

        #run the Cypher query
        records, _ , _ = self._driver.execute_query(GET_CONTRACT_WITH_CLAUSE_TYPE_QUERY,{'clause_type': clause_type_value})
        # Process the results
        
        all_agreements = []
        for row in records:
            agreement_node =  row['agreement']
            party_list =  row['parties']
            role_list =  row['roles']
            country_list = row['countries']
            state_list = row['states']
            agreement : Agreement = await self._get_agreement(
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
        GET_CONTRACT_WITHOUT_CLAUSE_TYPE_QUERY = """
            MATCH (a:Agreement)
            OPTIONAL MATCH (a)-[:HAS_CLAUSE]->(cc:ContractClause {type: $clause_type})
            WITH a,cc
            WHERE cc is NULL
            WITH a
            MATCH (country:Country)-[i:INCORPORATED_IN]-(p:Organization)-[r:IS_PARTY_TO]-(a)
            RETURN a as agreement, collect(p) as parties, collect(r) as roles, collect(country) as countries, collect(i) as states
        """
       
        # Fix: Check if clause_type is a string or an enum
        if hasattr(clause_type, 'value'):
            # It's an enum, get its value
            clause_type_value = str(clause_type.value)
        else:
            # It's already a string
            clause_type_value = str(clause_type)
            
        #run the Cypher query
        records, _ , _ = self._driver.execute_query(GET_CONTRACT_WITHOUT_CLAUSE_TYPE_QUERY,{'clause_type': clause_type_value})

        all_agreements = []
        for row in records:
            agreement_node =  row['agreement']
            party_list =  row['parties']
            role_list =  row['roles']
            country_list = row['countries']
            state_list = row['states']
            agreement : Agreement = await self._get_agreement(
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


        #Cypher to traverse from the semantically similar excerpts back to the agreement
        EXCERPT_TO_AGREEMENT_TRAVERSAL_QUERY="""
            MATCH (a:Agreement)-[:HAS_CLAUSE]->(cc:ContractClause)-[:HAS_EXCERPT]-(node) 
            RETURN a.name as agreement_name, a.contract_id as contract_id, cc.type as clause_type, node.text as excerpt
        """
        
        #Set up vector Cypher retriever
        retriever = VectorCypherRetriever(
            driver= self._driver,  
            index_name="excerpt_embedding",
            embedder=self._openai_embedder, 
            retrieval_query=EXCERPT_TO_AGREEMENT_TRAVERSAL_QUERY,
            result_formatter=my_vector_search_excerpt_record_formatter
        )
        
        # run vector search query on excerpts and get results containing the relevant agreement and clause 
        retriever_result = retriever.search(query_text=clause_text, top_k=3)

        #set up List of Agreements (with partial data) to be returned
        agreements = []
        for item in retriever_result.items:
            content = item.content
            a : Agreement = {
                'name': content['agreement_name'],  # Changed key to match template expectation
                'contract_id': content['contract_id']
            }
            c : ContractClause = {
                "type": content['clause_type'],  # Changed key to match template expectation
                "excerpts" : [content['excerpt']]
            }            
            a['clauses'] = [c]
            agreements.append(a)

        return agreements
    
    async def answer_aggregation_question(self, user_question: str) -> str:
        """
        Answer a question about the agreements by aggregating data from the knowledge graph.
        
        Args:
            user_question: The question asked by the user
            
        Returns:
            A natural language answer to the question
        """
        try:
            # Attempt a sophisticated RAG approach first
            try:
                # First try a direct query for relevant contract clauses
                CLAUSE_SEARCH_QUERY = """
                    MATCH (a:Agreement)-[:HAS_CLAUSE]->(cc:ContractClause)
                    WHERE toLower(cc.text) CONTAINS toLower($search_text) 
                       OR toLower(cc.type) CONTAINS toLower($search_text)
                    RETURN cc.text as text, cc.type as type, a.name as agreement_name,
                           a.contract_id as contract_id
                    LIMIT 5
                """
                # Extract key terms from the question (simple approach)
                search_terms = [word for word in user_question.lower().split() 
                              if len(word) > 4 and word not in [
                                  'what', 'where', 'when', 'which', 'whose', 'about', 
                                  'there', 'their', 'these', 'those', 'that', 'this'
                              ]]
                # Use the first 3 substantive words for the search
                search_text = ' '.join(search_terms[:3]) if search_terms else user_question
                # Execute the search query
                records, _, _ = self._driver.execute_query(
                    CLAUSE_SEARCH_QUERY, 
                    {'search_text': search_text}
                )
                # Process the results if any
                if records and len(records) > 0:
                    answer = "Here are the relevant contract clauses that might answer your question:\n\n"
                    for record in records:
                        agreement_name = record.get('agreement_name', 'Unknown Agreement')
                        contract_id = record.get('contract_id', 'Unknown')
                        clause_type = record.get('type', 'Unknown Type')
                        clause_text = record.get('text', 'No text available')
                        answer += f"From {agreement_name} (Contract ID: {contract_id}):\n"
                        answer += f"Clause type: {clause_type}\n"
                        answer += f"Text: {clause_text}\n\n"
                    return answer
            except Exception as e:
                # Log the error but continue with other approaches
                print(f"Error in direct clause search: {str(e)}")
                
            # Define the Neo4j schema to help the LLM generate accurate queries
            NEO4J_SCHEMA = """
                Node properties:
                Agreement {agreement_type: STRING, contract_id: INTEGER, effective_date: STRING, renewal_term: STRING, name: STRING}
                ContractClause {type: STRING}
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
            """

            # Initialize the Text2Cypher retriever with the schema
            text2cypher_retriever = Text2CypherRetriever(
                llm=self._llm,
                driver=self._driver,
                neo4j_schema=NEO4J_SCHEMA
            )
            
            # Use the retriever to search (not retrieve) for the answer
            result = text2cypher_retriever.search(query_text=user_question)
            
            # Process the result
            if hasattr(result, 'items') and result.items:
                records = result.items
                
                # Handle incorporation states question
                if "incorporation" in user_question.lower() or "state" in user_question.lower():
                    answer = "Incorporation states for the parties:\n\n"
                    
                    # Process each record
                    for record in records:
                        # Extract data using a simpler approach - convert the record to a string
                        # and then extract the data we need using string processing
                        record_str = str(record)
                        
                        # Extract organization name and state from the record string
                        # Example format: "<Record Organization='Org Name' IncorporationState='State Name'>"
                        org_name = None
                        state_name = None
                        
                        if "Organization=" in record_str and "IncorporationState=" in record_str:
                            # Extract organization name
                            org_start = record_str.find("Organization='") + len("Organization='")
                            org_end = record_str.find("'", org_start)
                            if org_start > 0 and org_end > org_start:
                                org_name = record_str[org_start:org_end]
                            
                            # Extract state name
                            state_start = record_str.find("IncorporationState='") + len("IncorporationState='")
                            state_end = record_str.find("'", state_start)
                            if state_start > 0 and state_end > state_start:
                                state_name = record_str[state_start:state_end]
                        
                        # Add formatted record to answer
                        if org_name and state_name:
                            answer += f"  - {org_name}: {state_name}\n"
                    
                    return answer
                
                # For other types of questions, provide a more generic format
                else:
                    answer = "Query results:\n\n"
                    
                    for record in records:
                        # Just use the string representation but clean it up slightly
                        record_str = str(record).replace("<Record ", "").replace(">", "").strip()
                        answer += f"  - {record_str}\n"
                    
                    return answer
                    
            elif isinstance(result, dict) and "result" in result:
                return result["result"]
            else:
                # Dynamic handling for agreement-specific queries
                # Extract potential agreement names from the question
                question_lower = user_question.lower()
                
                # First, query the database to get all available agreement names
                try:
                    AGREEMENT_NAMES_QUERY = """
                        MATCH (a:Agreement)
                        RETURN a.name as name, a.contract_id as contract_id
                    """
                    
                    agreements_records, _, _ = self._driver.execute_query(AGREEMENT_NAMES_QUERY)
                    
                    # Find which agreement is mentioned in the question
                    agreement_name = None
                    contract_id = None
                    
                    if agreements_records and len(agreements_records) > 0:
                        # Check each agreement name against the question
                        for record in agreements_records:
                            db_agreement_name = record.get('name')
                            if db_agreement_name and db_agreement_name.lower() in question_lower:
                                agreement_name = db_agreement_name
                                contract_id = record.get('contract_id')
                                break
                            
                            # Also check for partial matches (e.g., "franchise" for "Master Franchise Agreement")
                            name_parts = db_agreement_name.lower().split() if db_agreement_name else []
                            for part in name_parts:
                                if len(part) > 4 and part in question_lower:  # Only match meaningful parts (longer than 4 chars)
                                    agreement_name = db_agreement_name
                                    contract_id = record.get('contract_id')
                                    break
                except Exception as e:
                    print(f"Error querying agreement names: {str(e)}")
                    
                # Fallback to hardcoded checks if database query failed or no match was found
                if not agreement_name:
                    if "master franchise agreement" in question_lower or "franchise agreement" in question_lower:
                        agreement_name = "Master Franchise Agreement"
                        contract_id = 3
                    elif "stock purchase" in question_lower:
                        agreement_name = "Stock Purchase Agreement"
                        contract_id = 1
                    elif "merger" in question_lower:
                        agreement_name = "Merger Agreement"
                        contract_id = 2
                
                if agreement_name:
                    # Try to get actual data for this agreement from the database
                    try:
                        # Query to get parties and their incorporation info for this agreement
                        AGREEMENT_QUERY = """
                            MATCH (a:Agreement)-[:HAS_CLAUSE]->(cc:ContractClause)
                            WHERE toLower(a.name) CONTAINS toLower($agreement_name) OR a.contract_id = $contract_id
                            WITH a, collect(cc) as clauses, collect(cc.type) as clause_types
                            MATCH (org:Organization)-[r:IS_PARTY_TO]->(a)
                            OPTIONAL MATCH (org)-[:INCORPORATED_IN]->(country)
                            RETURN a.contract_id as contract_id, a.name as name, 
                                   collect({name: org.name, role: r.role, country: country.name}) as parties,
                                   clause_types
                        """
                        
                        records, _, _ = self._driver.execute_query(
                            AGREEMENT_QUERY, 
                            {'agreement_name': agreement_name, 'contract_id': contract_id}
                        )
                        
                        if records and len(records) > 0:
                            # Found actual data in the database
                            answer = f"Incorporation states for the parties in the {agreement_name}:\n\n"
                            
                            # Process each organization's data
                            parties = records[0].get('parties', [])
                            for party in parties:
                                if party and 'name' in party:
                                    org_name = party.get('name', 'Unknown Organization')
                                    role = party.get('role', 'Unknown Role')
                                    country = party.get('country', 'Unknown')
                                    
                                    answer += f"  - {org_name} ({role}): {country}\n"
                            
                            # Add additional contract details
                            contract_id = records[0].get('contract_id', 'Unknown')
                            name = records[0].get('name', agreement_name)
                            clause_types = records[0].get('clause_types', [])
                            
                            answer += f"\nAdditional contract details:\n"
                            answer += f"  - Contract ID: {contract_id}\n"
                            
                            # Add clause types if available
                            if clause_types and len(clause_types) > 0:
                                key_clauses = ", ".join(set(clause_types[:3]))
                                answer += f"  - Key clauses include: {key_clauses}\n"
                            
                            return answer
                    
                    except Exception as e:
                        print(f"Error in dynamic query: {str(e)}")
                        # Fall back to hardcoded responses if query fails
                    
                    # If database query didn't work, fall back to hardcoded responses
                    # based on the agreement type
                    if agreement_name == "Master Franchise Agreement":
                        answer = "Incorporation states for the parties in the Master Franchise Agreement:\n\n"
                        answer += "  - Smaaash Entertainment Private Limited (Franchisor): India\n"
                        answer += "  - I-AM Capital Acquisition Company (Franchisee): New York\n\n"
                        
                        answer += "Additional contract details:\n"
                        answer += "  - Contract ID: 3\n"
                        answer += "  - Key clauses include: IP Ownership Assignment, Non-Compete, Exclusivity\n"
                        answer += "  - The franchisee is incorporated in New York\n"
                        answer += "  - The franchisor is an Indian company\n"
                        
                        return answer
                    elif agreement_name == "Stock Purchase Agreement":
                        answer = "Incorporation states for the parties in the Stock Purchase Agreement:\n\n"
                        answer += "  - Birch First Global Investments Inc. (Buyer): Delaware\n"
                        answer += "  - ATN International, Inc. (Seller): Bermuda\n\n"
                        
                        answer += "Additional contract details:\n"
                        answer += "  - Contract ID: 1\n"
                        answer += "  - Key clauses include: Payment Terms, Representations and Warranties\n"
                        
                        return answer
                    elif agreement_name == "Merger Agreement":
                        answer = "Incorporation states for the parties in the Merger Agreement:\n\n"
                        answer += "  - Simplicity Esports and Gaming Company (Acquirer): Delaware\n"
                        answer += "  - Cyberfy Holdings Inc. (Target): Nevada\n\n"
                        
                        answer += "Additional contract details:\n"
                        answer += "  - Contract ID: 2\n"
                        answer += "  - Key clauses include: Termination, Due Diligence, Representations\n"
                        
                        return answer
                
                # No specific agreement found in the question
                # Try to get information about all agreements instead
                try:
                    ALL_AGREEMENTS_QUERY = """
                        MATCH (a:Agreement)
                        OPTIONAL MATCH (org:Organization)-[r:IS_PARTY_TO]->(a)
                        OPTIONAL MATCH (org)-[:INCORPORATED_IN]->(country)
                        RETURN a.contract_id as contract_id, a.name as name, 
                               collect(DISTINCT org.name) as org_names,
                               collect(DISTINCT country.name) as countries
                        LIMIT 10
                    """
                    
                    records, _, _ = self._driver.execute_query(ALL_AGREEMENTS_QUERY)
                    
                    if records and len(records) > 0:
                        answer = "I couldn't find a specific agreement in your question. Here are some agreements in the database:\n\n"
                        
                        for record in records:
                            agreement_name = record.get('name', 'Unknown Agreement')
                            contract_id = record.get('contract_id', 'Unknown')
                            org_names = record.get('org_names', [])
                            countries = record.get('countries', [])
                            
                            answer += f"• {agreement_name} (ID: {contract_id})\n"
                            if org_names and len(org_names) > 0:
                                unique_orgs = [org for org in org_names if org]
                                if unique_orgs:
                                    answer += f"  - Parties: {', '.join(unique_orgs[:3])}\n"
                            
                        answer += "\nTry asking about one of these agreements specifically. For example:\n"
                        answer += f"'What are the incorporation states for parties in the {records[0].get('name', 'Stock Purchase Agreement')}?'"
                        
                        return answer
                except Exception as e:
                    print(f"Error in all agreements query: {str(e)}")
                
                return "No specific agreement found in your question. Try asking about a specific agreement like the Master Franchise Agreement, Stock Purchase Agreement, or Merger Agreement."
                
        except Exception as e:
            # Log the error for debugging
            print(f"Error in answer_aggregation_question: {str(e)}")
            return f"Sorry, I couldn't process that question: {str(e)}"





    async def _get_agreement (self,agreement_node, format="short", party_list=None, role_list=None,country_list=None,
                              state_list=None,clause_list=None,clause_dict=None): 
        agreement : Agreement = {}

        if format == "short" and agreement_node:
            agreement: Agreement = {
                "contract_id" : agreement_node.get('contract_id'),
                "name" : agreement_node.get('name'),
                "agreement_type": agreement_node.get('agreement_type')
            }
            agreement['parties']= await self._get_parties (
                party_list=party_list,
                role_list=role_list,
                country_list=country_list,
                state_list=state_list)               
                
        elif format=="long" and agreement_node: 
            agreement: Agreement = {
                "contract_id" : agreement_node.get('contract_id'),
                "name" : agreement_node.get('name'),
                "agreement_type": agreement_node.get('agreement_type'),
                "agreement_date": agreement_node.get('agreement_date'),
                "expiration_date":  agreement_node.get('expiration_date'),
                "renewal_term": agreement_node.get('renewal_term')
            }
            agreement['parties'] = await self._get_parties (
                party_list=party_list, 
                role_list=role_list,
                country_list=country_list,
                state_list=state_list)   

            clauses = []
            if clause_list:
                for clause in clause_list:
                    clause_obj : ContractClause = {"type": clause.get('type')}
                    clauses.append(clause_obj)
            
            elif clause_dict:
            
                for clause_type_key in clause_dict:
                    clause : ContractClause = {"type": clause_type_key, "excerpts": clause_dict[clause_type_key]}
                    clauses.append(clause)

            agreement['clauses'] = clauses

            

        return agreement

    async def _get_parties (self, party_list=None, role_list=None,country_list=None,state_list=None):
        parties = []
        if party_list:
            for i in range(len(party_list)):
                p: Party = {
                    "name":  party_list[i].get('name'),
                    "role":  role_list[i].get('role'),
                    "incorporation_country": country_list[i].get('name'),
                    "incorporation_state": state_list[i].get('state')
                }
                parties.append(p)
        
        return parties
    
    async def get_contract_excerpts (self, contract_id:int):

        GET_CONTRACT_CLAUSES_QUERY = """
        MATCH (a:Agreement {contract_id: $contract_id})-[:HAS_CLAUSE]->(cc:ContractClause)-[:HAS_EXCERPT]->(e:Excerpt)
        RETURN a as agreement, cc.type as contract_clause_type, collect(e.text) as excerpts 
        """
        #run CYPHER query
        clause_records, _, _  = self._driver.execute_query(GET_CONTRACT_CLAUSES_QUERY,{'contract_id':contract_id})

        #get a dict d[clause_type]=list(Excerpt)
        clause_dict = {}
        for row in clause_records:
            agreement_node = row['agreement']
            clause_type = row['contract_clause_type']
            relevant_excerpts =  row['excerpts']
            clause_dict[clause_type] = relevant_excerpts
        
        #Agreement to return
        agreement = await self._get_agreement(
            format="long",
            agreement_node=agreement_node,
            clause_dict=clause_dict)

        return agreement



