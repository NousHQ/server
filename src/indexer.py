from langchain.text_splitter import RecursiveCharacterTextSplitter
from requests import RequestException
import time

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

    # print("[*] Prepped document: ", uri)

    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)

    MAX_RETRIES = 5
    RETRY_DELAY = 2
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            if not client.schema.exists(source_class):
                print("[!] Schema doesn't exist. Initializing...")
                logger.info(f"Initializing {user_id} schema")
                knowledge_source = {
                    "class": source_class,
                    "description": "A source saved by the user",
                    "properties": [
                        {
                            "name": "uri",
                            "description": "The URI of the source",
                            "dataType": ["text"],
                        },
                        {
                            "name": "title",
                            "description": "The title of the source",
                            "dataType": ["text"]
                        }
                    ]
                }

                content = {
                    "class": content_class,
                    "description": "The content of a source",
                    "properties": [
                        {
                            "name": "source_content",
                            "dataType": ["text"]
                        },
                        {
                            "name": "hasCategory",
                            "dataType": [source_class],
                            "description": "The source of the knowledge"
                        }
                    ],
                    # "vectorizer": "text2vec-huggingface",
                    "vectorizer": "text2vec-openai",
                    "moduleConfig": {
                        "reranker-cohere": {
                            "model": "rerank-english-v2.0"
                        },
                        "text2vec-openai": {
                            "model": "ada",
                            "modelVersion": "002",
                            "type": "text"
                        # "text2vec-huggingface": {
                        #     "model": "intfloat/e5-large-v2",
                        #     "options": {
                        #         "waitForModel": "true"
                        #     },
                        }
                    }
                    # "moduleConfig": {
                    #     }
                    # }
                }
                client.schema.create({"classes": [knowledge_source, content]})
            break
        except RequestException.exceptions.ConnectionError as e:
            logger.error(f"Connection error: checking {user_id} schema")
            time.sleep(RETRY_DELAY)
            retry_count += 1
    
    if retry_count == MAX_RETRIES:
        logger.error(f"Failed to initialize schema for {user_id}")
        raise get_failed_exception()


    client.batch.configure(batch_size=50, num_workers=1)
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