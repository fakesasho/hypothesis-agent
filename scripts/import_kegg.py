import xml.etree.ElementTree as ET
from neo4j import GraphDatabase
import logging
import os
import argparse

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KEGGImporter:

    def __init__(self, uri, user, password):
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            logger.info("Successfully connected to Neo4j.")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        try:
            self.driver.close()
            logger.info("Neo4j connection closed.")
        except Exception as e:
            logger.error(f"Failed to close Neo4j connection: {e}")

    def import_kegg_xml(self, xml_files):
        with self.driver.session() as session:
            for xml_file in xml_files:
                try:
                    logger.info(f"Importing {xml_file}...")
                    tree = ET.parse(xml_file)
                    root = tree.getroot()

                    # start a id to name mapping
                    id_to_name = {}

                    # Extract pathway IDs and titles associated with the entry
                    pathway_ids = []
                    pathway_titles = []
                    pathway_id = root.get('name')
                    pathway_title = root.get('title')
                    if pathway_id and pathway_title:
                        pathway_ids.append(pathway_id)
                        pathway_titles.append(pathway_title)

                    for entry in root.findall('entry'):
                        try:
                            entry_id = entry.get('id')
                            kegg_name = entry.get('name')
                            entry_type = entry.get('type')  # Extract the type attribute
                            node_label = entry_type if entry_type else 'Entry'  # Use type as node label or default to 'Entry'

                            # Process graphics name into gene_names list
                            graphics = entry.find('graphics')
                            if graphics is not None and 'name' in graphics.attrib and isinstance(graphics.get('name'), str):
                                gene_names = graphics.get('name').replace(',', '').replace('.', '').split(' ')
                                entry_name = gene_names[0] if gene_names else kegg_name
                            else:
                                gene_names = []
                                entry_name = kegg_name

                            # add the name to id mapping
                            if entry_name:
                                id_to_name[entry_id] = entry_name

                            # Create or update entry node with pathway IDs, titles, and type
                            session.write_transaction(self._create_or_update_entry_node, entry_name,
                                                      kegg_name, gene_names, pathway_ids, pathway_titles, node_label)

                        except Exception as e:
                            logger.error(f"Failed to process entry in {xml_file}: {e}")

                    # Process relations after all entries are created
                    for relation in root.findall('relation'):
                        try:
                            entry1 = id_to_name[relation.get('entry1')]
                            entry2 = id_to_name[relation.get('entry2')]
                            relation_type = relation.get('type')
                            # set the subtype to be the same as the supertype by default
                            relation_subtype = relation_type
                            # find the name of the subtype element in the relation
                            if relation.find('subtype') is not None:
                                relation_subtype = relation.find('subtype').get('name')

                            # Create or update relationship between entries
                            session.write_transaction(self._create_relation, entry1, entry2, relation_type,
                                                      relation_subtype)
                        except Exception as e:
                            logger.error(f"Failed to process relation in {xml_file}: {entry1} {entry2} {relation_type} {e} exception type {type(e)}")
                            logger.error(f"Failed to process relation in {xml_file}: {e}")

                    # Run the post-processing step to remove duplicate gene names
                    try:
                        session.write_transaction(self._remove_duplicate_gene_names)
                        logger.info(f"Post-processing to remove duplicate gene names completed for {xml_file}.")
                    except Exception as e:
                        logger.error(f"Failed to remove duplicate gene names in {xml_file}: {e}")

                except ET.ParseError as e:
                    logger.error(f"Failed to parse XML file {xml_file}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error during import of {xml_file}: {e}")

    @staticmethod
    def _create_or_update_entry_node(tx, entry_name, kegg_name, gene_names, pathway_ids, pathway_titles, node_label):
        try:
            query = f"""
                MERGE (e:{node_label} {{entry_name: $entry_name}})
                ON CREATE SET e.name = $entry_name, 
                              e.gene_names = $gene_names,
                              e.pathway_ids = $pathway_ids, 
                              e.pathway_titles = $pathway_titles
                ON MATCH SET e.gene_names = apoc.coll.toSet(e.gene_names + $gene_names),
                              e.pathway_ids = apoc.coll.toSet(e.pathway_ids + $pathway_ids), 
                              e.pathway_titles = apoc.coll.toSet(e.pathway_titles + $pathway_titles)
            """
            tx.run(query, kegg_name=kegg_name, entry_name=entry_name, gene_names=gene_names,
                   pathway_ids=pathway_ids, pathway_titles=pathway_titles)
        except Exception as e:
            logger.error(f"Failed to create or update {node_label} node: {e}")
            raise

    @staticmethod
    def _create_relation(tx, entry1, entry2, relation_type, relation_subtype):
        def escape_relation(relation):
            return relation.replace(' ', '_').replace('/', '_or_')
        try:
            # Dynamically construct the relationship type part of the query
            query = f"""
                MATCH (e1 {{name: $entry1}})
                WITH e1
                MATCH (e2 {{name: $entry2}})
                MERGE (e1)-[r:{escape_relation(relation_subtype)}]->(e2)
                SET r.supertype = $relation_type
            """
            tx.run(query, entry1=entry1, entry2=entry2, relation_type=relation_type)
        except Exception as e:
            logger.error(f"Failed to create relation of type {relation_type} with subtype {relation_subtype}: {e}")
            raise

    @staticmethod
    def _remove_duplicate_gene_names(tx):
        try:
            tx.run("""
                MATCH (e)
                WITH e, apoc.coll.toSet(e.gene_names) AS unique_gene_names
                SET e.gene_names = unique_gene_names
            """)
        except Exception as e:
            logger.error(f"Failed to remove duplicate gene names: {e}")
            raise

    def test_import(self):
        """
        Run a test query to check if the import was successful. This test checks if the INSR node has at least 2
        pathway titles.

        Raises:
            ValueError: If the INSR node is not found or does not have at least 2 pathway titles.
        """
        with self.driver.session() as session:

            logger.info("Running import tests...")

            # test 1: check if the INSR node has at least 2 pathway titles
            result = session.run('MATCH (n {name: "INSR"}) RETURN n.pathway_titles AS pathway_titles')
            record = result.single()

            assert record is not None, "INSR node not found in the database."

            pathway_titles = record['pathway_titles']
            count = len(pathway_titles)

            assert count > 1, f"Expected at least 2 pathway titles for INSR, but found {count}. Pathway titles: {pathway_titles}"

            # test 2: check if the INSR has a subtree larger than 1
            result = session.run('MATCH (n {name: "INSR"})-[*]->(m) RETURN count(distinct m) AS subtree_size')
            record = result.single()

            assert record is not None, "INSR node does not have any descendants."

            subtree_size = record['subtree_size']
            assert subtree_size > 1, f"Expected subtree size for INSR to be greater than 1, found {subtree_size}."

        logger.info("Import test passed successfully.")


if __name__ == "__main__":
    # Load defaults from environment variables
    default_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    default_user = os.getenv('NEO4J_USER', 'neo4j')
    default_password = os.getenv('NEO4J_PASSWORD', 'supersafepassword')

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Import KEGG XML files into a Neo4j database.")
    parser.add_argument('-u', '--uri', type=str, default=default_uri,
                        help='Neo4j URI (default from environment variable NEO4J_URI)')
    parser.add_argument('-n', '--user', type=str, default=default_user,
                        help='Neo4j username (default from environment variable NEO4J_USER)')
    parser.add_argument('-p', '--password', type=str, default=default_password,
                        help='Neo4j password (default from environment variable NEO4J_PASSWORD)')
    parser.add_argument('-f', '--file', type=str, help='Path to a single KEGG XML file to import')
    parser.add_argument('-d', '--directory', type=str, help='Directory containing multiple KEGG XML files to import')

    args = parser.parse_args()

    # Ensure at least one input method is provided
    if not args.file and not args.directory:
        parser.error('No input source specified. Please provide either a file or a directory.')

    # Collect the files to process
    kegg_xml_files = []
    if args.file:
        kegg_xml_files.append(args.file)
    if args.directory:
        for file_name in os.listdir(args.directory):
            if file_name.endswith('.xml'):
                kegg_xml_files.append(os.path.join(args.directory, file_name))

    # Initialize the importer and process the files
    importer = None
    try:
        importer = KEGGImporter(args.uri, args.user, args.password)
        importer.import_kegg_xml(kegg_xml_files)
        importer.test_import()
    except ValueError as e:
        logger.error(f"An error occurred during the import process: {e}")
    except Exception as e:
        logger.error(f"An error occurred during the import process: {e}")
    finally:
        if importer:
            importer.close()
