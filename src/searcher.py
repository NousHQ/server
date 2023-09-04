from config import settings
from client import get_weaviate_client
from weaviate.gql.get import HybridFusion
from weaviate.exceptions import UnexpectedStatusCodeException
from fastapi import HTTPException, status
from functools import lru_cache

# no_schema_exception = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You haven't saved anything!")

@lru_cache
def get_failed_exception():
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You haven't saved anything!")

def searcher(query: str, user_id: str):
    client = get_weaviate_client()
    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)
    # TODO: better way to handle this
    # query = "query: " + query
    try:
        response = (
            client.query.get(
                content_class,
                [f"hasCategory {{ ... on {source_class} {{ uri title}}}}"])
                .with_hybrid(query=query, alpha=0.75, fusion_type=HybridFusion.RELATIVE_SCORE)
                .with_additional("score")
                .with_autocut(1)
                .do()
        )
    except UnexpectedStatusCodeException as e:
        print(e)
        raise get_failed_exception()
    print(response)
    results = []
    unique_uris_titles = set()
    try:
        for i, r in enumerate(response["data"]["Get"][content_class]):
            uri = r["hasCategory"][0]["uri"]
            title = r["hasCategory"][0]["title"]
            if (uri, title) not in unique_uris_titles:
                unique_uris_titles.add((uri, title))
                results.append({
                    "index": i,
                    "uri": r["hasCategory"][0]["uri"],
                    "title": r["hasCategory"][0]["title"],
                })

        return results
    except KeyError as e:
        print(e)
        raise get_failed_exception()