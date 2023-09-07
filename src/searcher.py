from config import settings
from logger import get_logger
from utils import get_no_schema_failed_exception, get_failed_exception, get_bad_search_exception

from client import get_weaviate_client
from weaviate.gql.get import HybridFusion
import json

logger = get_logger(__name__)

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
    except Exception as e:
        logger.error(f"Error {e} in searching '{query}' for {user_id}: Couldn't execute query")
        raise get_failed_exception()

    if "data" not in response:
        logger.info(f"{user_id} has no schema.")
        raise get_no_schema_failed_exception()

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

        return response, results

    except TypeError as te:
        logger.error(f"Error {te} in searching '{query}' for {user_id}: Content wasn't saved properly")
        raise get_bad_search_exception()

    except Exception as e:
        logger.error(f"Error {e} in searching '{query}' for {user_id}: Couldn't parse response")
        raise get_failed_exception()


def log_search(user_id, query, response):
    with open("query_logs.json", "a") as fd:
        entry_dict = {"user_id": user_id,
                      "query": query,
                      "response": response}
        entry = json.dumps(entry_dict)
        fd.write(entry + "\n")