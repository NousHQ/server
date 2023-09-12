from langchain.text_splitter import RecursiveCharacterTextSplitter
from requests import RequestException

from logger import get_logger
from config import settings
from client import get_weaviate_client
from utils import get_failed_exception

logger = get_logger(__name__)


def preprocess(document: dict):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1024)
    texts = text_splitter.split_text(document["content"])
    return texts


def indexer(data: dict, user_id: str):
    client = get_weaviate_client()
    document = data["pageData"]
    title = document["title"]
    uri = document["url"]

    logger.info(f"{user_id} saving {uri}")

    document["chunked_content"] = [title]
    document["chunked_content"].extend(preprocess(document))

    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)

    client.batch.configure(batch_size=50, num_workers=1, timeout_retries=3, connection_error_retries=3)
    with client.batch as batch:
        try:
            parent_uuid = batch.add_data_object(
                data_object={
                    'uri': uri,
                    'title': title
                },
                class_name=source_class
            )
            for i, chunk in enumerate(document["chunked_content"]):
                # TODO: better way to handle passage
                # chunk = "passage: " + chunk
                chunk_uuid = batch.add_data_object(
                    data_object={
                        'source_content': chunk,
                    },
                    class_name=content_class,
                )
                batch.add_reference(
                    from_object_uuid=chunk_uuid,
                    from_property_name="hasCategory",
                    to_object_uuid=parent_uuid,
                    from_object_class_name=content_class,
                    to_object_class_name=source_class
                )
        except Exception as e:
            logger.error(f"Error {e} in indexing {uri} for {user_id}")
            raise get_failed_exception()

    logger.info(f"Successfully saved {uri} for {user_id}")
    return True