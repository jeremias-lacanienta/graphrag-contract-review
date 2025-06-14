#!/usr/bin/env python3
"""
Database Optimization Script for GraphRAG Contract Review System

This script creates the necessary indexes and optimizations for the Neo4j database
to ensure optimal performance when querying contract data.

Run this once after setting up your database and loading contract data.
"""

import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase

def create_database_optimizations():
    """Create all necessary indexes and optimizations for the contract database"""
    
    # Load environment variables
    load_dotenv()
    
    # Database connection details
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
    
    if not NEO4J_PASSWORD:
        print("❌ Error: NEO4J_PASSWORD not found in environment variables")
        print("   Please set your Neo4j password in the .env file")
        sys.exit(1)
    
    print("🔧 Initializing database optimizations...")
    print(f"   Connecting to: {NEO4J_URI}")
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            # Node indexes for fast lookups
            node_indexes = [
                "CREATE INDEX agreement_contract_id IF NOT EXISTS FOR (a:Agreement) ON (a.contract_id)",
                "CREATE INDEX organization_name IF NOT EXISTS FOR (o:Organization) ON (o.name)",
                "CREATE INDEX clause_type IF NOT EXISTS FOR (c:ContractClause) ON (c.type)",
                "CREATE INDEX country_name IF NOT EXISTS FOR (c:Country) ON (c.name)",
            ]
            
            # Relationship indexes for traversal optimization
            relationship_indexes = [
                "CREATE INDEX party_role IF NOT EXISTS FOR ()-[r:IS_PARTY_TO]-() ON (r.role)",
                "CREATE INDEX governing_state IF NOT EXISTS FOR ()-[r:GOVERNED_BY_LAW]-() ON (r.state)",
                "CREATE INDEX incorporation_state IF NOT EXISTS FOR ()-[r:INCORPORATED_IN]-() ON (r.state)",
            ]
            
            # Composite indexes for complex queries
            composite_indexes = [
                "CREATE INDEX agreement_type_date IF NOT EXISTS FOR (a:Agreement) ON (a.agreement_type, a.effective_date)",
            ]
            
            all_indexes = node_indexes + relationship_indexes + composite_indexes
            
            print("📊 Creating database indexes...")
            for i, index_query in enumerate(all_indexes, 1):
                try:
                    session.run(index_query)
                    index_name = index_query.split()[2]
                    print(f"   ✓ [{i}/{len(all_indexes)}] {index_name}")
                except Exception as e:
                    print(f"   ⚠️  Index creation warning: {e}")
            
            # Get database statistics
            print("\n📈 Database Statistics:")
            
            # Count nodes
            node_counts = session.run("""
                MATCH (n) 
                RETURN labels(n)[0] as label, count(n) as count 
                ORDER BY count DESC
            """).data()
            
            for record in node_counts:
                label = record.get('label', 'Unknown')
                count = record.get('count', 0)
                print(f"   • {label}: {count:,} nodes")
            
            # Count relationships
            rel_counts = session.run("""
                MATCH ()-[r]->() 
                RETURN type(r) as relationship, count(r) as count 
                ORDER BY count DESC
            """).data()
            
            total_relationships = sum(record.get('count', 0) for record in rel_counts)
            print(f"   • Total Relationships: {total_relationships:,}")
            
            # Check for any existing indexes
            print("\n🗂️  Active Database Indexes:")
            existing_indexes = session.run("SHOW INDEXES").data()
            for index in existing_indexes:
                name = index.get('name', 'Unknown')
                state = index.get('state', 'Unknown')
                print(f"   • {name}: {state}")
            
        print("\n✅ Database optimization complete!")
        print("   Your Neo4j database is now optimized for contract queries.")
        print("   You can now use the contract review applications with improved performance.")
        
    except Exception as e:
        print(f"\n❌ Error during optimization: {e}")
        print("   Please check your Neo4j connection and try again.")
        sys.exit(1)
        
    finally:
        driver.close()

def check_optimization_status():
    """Check if database optimizations have been applied"""
    load_dotenv()
    
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
    
    if not NEO4J_PASSWORD:
        return False
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            # Check for key indexes that should exist
            indexes = session.run("SHOW INDEXES").data()
            existing_index_names = [idx.get('name', '').lower() for idx in indexes]
            
            # Check if the core indexes exist (case-insensitive partial matching)
            required_patterns = ['agreement', 'organization', 'clause']
            found_patterns = 0
            
            for pattern in required_patterns:
                if any(pattern in name for name in existing_index_names):
                    found_patterns += 1
            
            # Consider optimized if at least 2/3 core patterns are found
            return found_patterns >= 2
    except:
        return False
    finally:
        driver.close()

def run_quiet_optimization():
    """Run optimizations with minimal output for shell script integration"""
    load_dotenv()
    
    NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
    NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
    
    if not NEO4J_PASSWORD:
        print("❌ Error: NEO4J_PASSWORD not found in environment variables")
        return False
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    try:
        # Check if optimizations are already applied
        if check_optimization_status():
            print("✅ Database optimizations verified")
            return True
        
        print("🔧 Applying database optimizations...")
        
        with driver.session() as session:
            # Apply all indexes quietly
            all_indexes = [
                "CREATE INDEX agreement_contract_id IF NOT EXISTS FOR (a:Agreement) ON (a.contract_id)",
                "CREATE INDEX organization_name IF NOT EXISTS FOR (o:Organization) ON (o.name)",
                "CREATE INDEX clause_type IF NOT EXISTS FOR (c:ContractClause) ON (c.type)",
                "CREATE INDEX country_name IF NOT EXISTS FOR (c:Country) ON (c.name)",
                "CREATE INDEX party_role IF NOT EXISTS FOR ()-[r:IS_PARTY_TO]-() ON (r.role)",
                "CREATE INDEX governing_state IF NOT EXISTS FOR ()-[r:GOVERNED_BY_LAW]-() ON (r.state)",
                "CREATE INDEX incorporation_state IF NOT EXISTS FOR ()-[r:INCORPORATED_IN]-() ON (r.state)",
                "CREATE INDEX agreement_type_date IF NOT EXISTS FOR (a:Agreement) ON (a.agreement_type, a.effective_date)",
            ]
            
            for index_query in all_indexes:
                try:
                    session.run(index_query)
                except:
                    pass  # Ignore errors for existing indexes
        
        print("✅ Database optimization complete")
        return True
        
    except Exception as e:
        print(f"⚠️  Optimization warning: {e}")
        return False
    finally:
        driver.close()

if __name__ == "__main__":
    # Check if running with --quiet flag for shell script integration
    if len(sys.argv) > 1 and sys.argv[1] == "--quiet":
        run_quiet_optimization()
    else:
        print("=" * 60)
        print("  GraphRAG Contract Review - Database Optimization")
        print("=" * 60)
        
        # Check if optimizations are already applied
        if check_optimization_status():
            print("✅ Database optimizations are already in place!")
            print("   Your Neo4j database is optimized for contract queries.")
            
            # Still show current statistics
            load_dotenv()
            NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
            NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
            NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
            
            if NEO4J_PASSWORD:
                driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                try:
                    with driver.session() as session:
                        node_counts = session.run("""
                            MATCH (n) 
                            RETURN labels(n)[0] as label, count(n) as count 
                            ORDER BY count DESC
                        """).data()
                        
                        print("\n📈 Current Database Statistics:")
                        for record in node_counts:
                            label = record.get('label', 'Unknown')
                            count = record.get('count', 0)
                            print(f"   • {label}: {count:,} nodes")
                except:
                    pass
                finally:
                    driver.close()
        else:
            create_database_optimizations()
