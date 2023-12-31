from config import settings
from logger import get_logger
from utils import get_no_schema_failed_exception, get_failed_exception, get_bad_search_exception

from client import query_weaviate_client
from weaviate.gql.get import HybridFusion


logger = get_logger(__name__)

def searcher(query: str, user_id: str):
    client = query_weaviate_client()
    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)
    # TODO: better way to handle this
    # query = "query: " + query

    try:
        response = (
            client.query.get(
                content_class,
                [f"hasCategory {{ ... on {source_class} {{ uri title _additional {{ id }}}}}}"])
                .with_hybrid(query=query, alpha=0.75, fusion_type=HybridFusion.RELATIVE_SCORE)
                # .with_additional("score")
                .with_additional(['rerank(property: "source_content", query: "{}") {{ score }}'.format(query), 'id'])
                .with_autocut(2)
                .do()
        )
    except Exception as e:
        logger.error(f"Error {e} in searching '{query}' for {user_id}: Couldn't execute query")
        raise get_failed_exception()

    if "errors" in response:
        logger.info(f"{user_id} error in querying: {response}")
        raise get_no_schema_failed_exception()

    results = []
    unique_uris_titles = set()
    try:
        for i, r in enumerate(response["data"]["Get"][content_class]):
            uri = r["hasCategory"][0]["uri"]
            title = r["hasCategory"][0]["title"]
            score = r["_additional"]["rerank"][0]["score"]
            source_id = r["hasCategory"][0]["_additional"]["id"]
            if score < 0.15:
                continue
            if (uri, title) not in unique_uris_titles:
                unique_uris_titles.add((uri, title))
                results.append({
                    "index": i,
                    "id": source_id,
                    "uri": uri,
                    "title": title
                })

        return response, results

    except TypeError as te:
        logger.error(f"Error {te} in searching '{query}' for {user_id}")
        raise get_bad_search_exception()

    except Exception as e:
        logger.error(f"Error {e} in searching '{query}' for {user_id}: Couldn't parse response")
        raise get_failed_exception()

