knowledge_source = {
    "class": "KnowledgeSourceId-{}",
    "description": "A source saved by the user",
    "properties": [
        {
            "name": "uri",
            "description": "The URI of the source",
            "dataType": ["text"],
        }
    ]
}

content = {
    "class": "ContentId-{}",
    "description": "The content of a source",
    "properties": [
        {
            "name": "source_content",
            "dataType": ["text"]
        },
        {
            "name": "hasCategory",
            "dataType": ["KnowledgeSource"],
            "description": "The source of the knowledge"
        }
    ],
    "vectorizer": "none",
    "moduleConfig": {
        "reranker-cohere": {
            "model": "rerank-english-v2.0"
        }
    }
}