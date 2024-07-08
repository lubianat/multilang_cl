import os
import requests
from rdflib import Graph, URIRef, Literal, RDF, RDFS, Namespace, BNode
from SPARQLWrapper import SPARQLWrapper, JSON
from tqdm import tqdm

OBO = Namespace("http://www.geneontology.org/formats/oboInOwl#")

selected_languages = ["fr", "es", "de", "pt", "it", "ar", "el", "ru", "ja", "zh"]


def fetch_wikidata_labels(query):
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()

    label_data = {}
    for result in results["results"]["bindings"]:
        ontology_id = result["obo_id"]["value"]
        wikidata_uri = result["item"]["value"]
        label_value = result["itemLabel"]["value"]
        label_lang = result["itemLabel_lang"]["value"]

        if ontology_id not in label_data:
            label_data[ontology_id] = {"wikidata_uri": wikidata_uri, "labels": {}}

        if label_lang in selected_languages:
            label_data[ontology_id]["labels"][label_lang] = label_value

    return label_data


def update_ontology_labels(file_path, label_data):
    graph = Graph()
    graph.parse(file_path, format="xml")

    for ontology_id, data in tqdm(label_data.items(), desc="Updating ontology"):
        ontology_uri = URIRef(ontology_id)
        wikidata_uri = URIRef(data["wikidata_uri"])

        if (ontology_uri, RDFS.label, None) in graph:
            for lang, label in data["labels"].items():
                label_literal = Literal(label, lang=lang)
                graph.add((ontology_uri, RDFS.label, label_literal))
                axiom_node = BNode()
                graph.add(
                    (
                        axiom_node,
                        RDF.type,
                        URIRef("http://www.w3.org/2002/07/owl#Axiom"),
                    )
                )
                graph.add(
                    (
                        axiom_node,
                        URIRef("http://www.w3.org/2002/07/owl#annotatedSource"),
                        ontology_uri,
                    )
                )
                graph.add(
                    (
                        axiom_node,
                        URIRef("http://www.w3.org/2002/07/owl#annotatedProperty"),
                        RDFS.label,
                    )
                )
                graph.add(
                    (
                        axiom_node,
                        URIRef("http://www.w3.org/2002/07/owl#annotatedTarget"),
                        label_literal,
                    )
                )
                graph.add((axiom_node, OBO.hasDbXref, wikidata_uri))
        else:
            print(f"No existing RDFS.label for {ontology_uri}")

    graph.serialize(destination="data/cl-multilingual.owl", format="xml")


def download_ontology(ontology_name):
    url = f"http://purl.obolibrary.org/obo/{ontology_name}.owl"
    local_file = f"data/{ontology_name}.owl"

    if not os.path.exists("data"):
        os.makedirs("data")

    if os.path.exists(local_file):
        response = requests.head(url)
        remote_size = int(response.headers.get("Content-Length", 0))
        local_size = os.path.getsize(local_file)

        if remote_size != local_size:
            print(
                f"Remote file size ({remote_size}) differs from local file size ({local_size}), downloading the file."
            )
            os.system(f"wget -nc -O {local_file} {url}")
        else:
            print("Local file is up to date.")
    else:
        os.system(f"wget -nc -O {local_file} {url}")


query = """
SELECT ?obo_id ?item ?itemLabel ?itemLabel_lang
WHERE {
  VALUES ?obo_props {wdt:P7963 wdt:P1554} .
  ?item ?obo_props ?obo_id_final .
  ?item rdfs:label ?itemLabel .
  BIND(URI(CONCAT("http://purl.obolibrary.org/obo/", ?obo_id_final)) as ?obo_id)
  BIND(LANG(?itemLabel) as ?itemLabel_lang)
}
"""

ontology_name = "cl"
download_ontology(ontology_name)
label_data = fetch_wikidata_labels(query)

# Debug: Print label data to verify correct fetching
for oid, data in label_data.items():
    print(f"Ontology ID: {oid}")
    print(f"Wikidata URI: {data['wikidata_uri']}")
    for lang, label in data["labels"].items():
        print(f" - {lang}: {label}")

update_ontology_labels(f"data/{ontology_name}.owl", label_data)
