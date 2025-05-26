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
        Process any user question by converting it to a Cypher query,
        executing it, and returning the results.
        """
        try:
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
                return "No results found for your question."
                
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



