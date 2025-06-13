# GraphRAG Contract Review - Agent Behavior Rules

## Core Rules
- Ask questions before making recommendations
- Respect data privacy and security
- Request clarification when uncertain
- Verify technical requirements before suggesting changes

## Communication
- Ask about preferred technical detail level
- Provide examples when helpful
- Reference specific file paths
- Focus on clear, direct responses

## Neo4j and GraphRAG
- Ask about schema changes
- Discuss query validation
- Verify approach for template modifications

## Neo4j and GraphRAG
- Ask about schema changes
- Discuss query validation
- Verify approach for template modifications

## Don't Do
- Do not modify any files outside of .tmp folder unless I instructed it
- Do not create additional files outside of .tmp folder unless I instructed it
- Do not create fallback behavior that is fixed  and will mask error

## Do
- Do create any file for testing purposes or validation inside .tmp folder
- Always ask permission if you need to modify any files outside of .tmp folder
- You can copy files from outside of .tmp folder to inside of .tmp folder if you need to modify and test it