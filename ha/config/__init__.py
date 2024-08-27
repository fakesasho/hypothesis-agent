import os


# Load Neo4j credentials from environment variables
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USER', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD', 'supersafepassword')

# Load OpenAI API key from environment variable
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_NEO4J_MODEL = os.getenv('OPENAI_NEO4J_MODEL', 'gpt-4o')
OPENAI_PANDAS_MODEL = os.getenv('OPENAI_PANDAS_MODEL', 'gpt-4o')
OPENAI_AGENT_MODEL = os.getenv('OPENAI_AGENT_MODEL', 'gpt-4o')

# File paths
PROJECT_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAF_FILE_PATH = os.getenv('GAF_FILE', os.path.join(PROJECT_PATH, 'data', 'gaf', 'goa_human.gaf'))

TOOL_DESCRIPTIONS = {
    "kegg_query":       "KEGG is a database of disease pathways stored in a Neo4j instance."
                        "The tool allows the retrieval of information about the signaling chains"
                        "between genes in a disease pathway. Use to find relationships between genes and diseases.",
    "gaf_query":        "The GAF database instance contains GO terms and annotations for "
                        "human genes. The tool allows queries using SQLite and the "
                        "standard GAF file headings.",
    "graph_analysis":   "The Graph Analysis gives you an informative network analysis about a gene symbol (node_name)"
                        "in the context of a disease pathway (pathway_title).\n"
                        "PREREQUISITES:\n"
                        "- node_name: this is the gene symbol from column 3 in GAF, e.g. INSR.\n"
                        "- pathway_title: this is typically the name of the disease, "
                        "but needs to be the same as defined in KEGG.\n"
}