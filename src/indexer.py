from config import settings
from weaviate import Client
from langchain.text_splitter import RecursiveCharacterTextSplitter


def preprocess(document: dict):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=512)
    texts = text_splitter.split_text(document["content"])
    return texts


def indexer(client: Client, data: dict, user_id: str):
    document = data["pageData"]
    title = document["title"]
    # uid = data["userData"]["userid"]

    uri = document["url"]
    document["chunked_content"] = preprocess(document)
    document["chunked_content"].append(title)

    print("[*] Prepped document: ", uri)

    source_class = settings.KNOWLEDGE_SOURCE_CLASS.format(user_id)
    content_class = settings.CONTENT_CLASS.format(user_id)

    if not client.schema.exists(source_class):
        print("[!] Schema doesn't exist. Initializing...")
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
            "vectorizer": "text2vec-openai",
            "moduleConfig": {
                "text2vec-openai": {
                    "model": "ada",
                    "modelVersion": "002",
                    "type": "text",
                }
            }
        }

        client.schema.create({"classes": [knowledge_source, content]})


    print("[*] Indexing document: ", uri)
    client.batch.configure(batch_size=50, num_workers=2)
    with client.batch as batch:
        total_chunks = len(document["chunked_content"])
        parent_uuid = batch.add_data_object(
            data_object={
                'uri': uri,
                'title': title
            },
            class_name=source_class
        )
        try:
            for i, chunk in enumerate(document["chunked_content"]):
                # TODO: better wat to handle passage
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
                print(f"[*] Added chunk no. {i} out of {total_chunks}")
        except Exception as e:
            print("[!] Failed to index document: ", uri, e)
            print(chunk)

    print("[!] Indexed document: ", uri)
    return True