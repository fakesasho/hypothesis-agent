import json
import logging
import warnings

import pandas as pd
import pandasql as ps
import requests

import ha.config as config
from ha.agent.executor import QueryExecutor
from ha.models import openai_client as client
from ha.utils import generative_execution, clean_markdown_response

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore")


gaf_column_names = [
    'DB', 'DB_Object_ID', 'DB_Object_Symbol', 'Qualifier', 'GO_ID', 'DB:Reference', 'Evidence', 'With', 'Aspect',
    'DB_Object_Name', 'Synonym', 'DB_Object_Type', 'Taxon', 'Date', 'Assigned_By', 'Annotation_Extension',
    'Gene_Product_Form_ID'
]

# GO annotation evidence codes
evidence_codes = {
    'EXP': 'Inferred from Experiment',
    'IDA': 'Inferred from Direct Assay',
    'IPI': 'Inferred from Physical Interaction',
    'IMP': 'Inferred from Mutant Phenotype',
    'IGI': 'Inferred from Genetic Interaction',
    'IEP': 'Inferred from Expression Pattern',
    'ISS': 'Inferred from Sequence or Structural Similarity',
    'ISO': 'Inferred from Sequence Orthology',
    'ISA': 'Inferred from Sequence Alignment',
    'ISM': 'Inferred from Sequence Model',
    'IGC': 'Inferred from Genomic Context',
    'IBA': 'Inferred from Biological aspect of Ancestor',
    'IBD': 'Inferred from Biological aspect of Descendant',
    'IKR': 'Inferred from Key Residues',
    'IRD': 'Inferred from Rapid Divergence',
    'RCA': 'Inferred from Reviewed Computational Analysis',
    'TAS': 'Traceable Author Statement',
    'NAS': 'Non-traceable Author Statement',
    'IC': 'Inferred by Curator',
    'ND': 'No biological Data available',
    'IEA': 'Inferred from Electronic Annotation',
    'NR': 'Not Recorded'
}

gaf_tips = """
- use the `DB_Object_Symbol` attribute to filter for gene symbols 
"""

class Gaf(QueryExecutor):

    NAME = "GAF Query Executor"

    def __init__(self, gaf_file_path: str = config.GAF_FILE_PATH, model: str =config.OPENAI_PANDAS_MODEL,
                 attempts: int = 3):
        super().__init__(model, attempts)
        self.data = self.load_data(gaf_file_path)

    @staticmethod
    def load_data(file_path: str) -> pd.DataFrame:
        """
        Load the data from the GAF file.

        Args:
            file_path: The path to the GAF file.

        Returns:
            The loaded data as a DataFrame
        """
        return pd.read_csv(file_path, sep='\t', comment='!', header=None, names=gaf_column_names, low_memory=False)


    def get_schema(self) -> str:
        """
        Get the schema of the GAF data.

        Returns:
            The schema of the GAF data from pandas.
        """
        # schema string
        schema_str = self.data.dtypes.to_string()
        return schema_str

    @generative_execution
    def generate_query(self, instruction: str, goal_template:str, reflection: str, schema: str,
                       limit: int = 10) -> tuple:
        """
        Method that uses OpenAI to generate a SQLite query given a pandas schema and a request.

        Args:
            instruction: The user's request.
            goal_template: The goal template for the query.
            reflection: The user's reflection on the previous response.
            schema: The pandas schema.
            limit: The number of rows to limit the output to.

        Returns:
            The generated Neo4j query and explanation.
        """
        # TODO: this could be abstracted through prompt parametrisation but too much work for now
        prompt = (f"Given the following pandas schema:\n{schema}\n"
                  f"The table name is 'gaf'.\n"
                  f"Use this reflection (if present): {reflection}\n"
                  f"And these tips: {gaf_tips}\n"
                  f"Take into account the goal data template if relevant: {goal_template}\n"
                  f"Generate an SQLite query that satisfies this instruction: {instruction}"
                  f"Unless otherwise instructed already, limit the output to {limit} rows.")

        # Send the image and text prompt to GPT-4 with Vision
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a system that generates queries using JSON template."
                                              "{'query': '<query here>', 'explanation': '<explanation here>'}."
                                              "You only respond with JSON."},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt}
                ]}
            ],
            response_format={"type": "json_object"}
        )

        # Extract the response from the assistant
        try:
            jsn = json.loads(clean_markdown_response(response.choices[0].message.content))
        except json.JSONDecodeError:
            raise ValueError("Failed to decode JSON response from OpenAI.")
        query = jsn["query"]
        explanation = jsn["explanation"]

        return query, explanation

    def execute_query(self, query: str) -> str:
        """
        Execute the query on the GAF data using SQLite on pandas data.

        Args:
            query: The query to execute.

        Returns:
            The result of the query.
        """
        try:
            logger.info(f"Executing query: {query}")
            gaf = self.data
            result = ps.sqldf(query, locals())
            return result.to_string()
        except ps.PandaSQLException as e:
            logger.error(f"SQL execution error: {e}")
            return f"SQL execution error: {e}"
        except KeyError as e:
            logger.error(f"Column not found: {e}")
            return f"Column not found in data: {e}"
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            return f"An unexpected error occurred: {e}"

    def simple_skill(self, gene_symbol: str, qualifier: str = None) -> str:
        """
        DEPRECATED: Filter the GAF data by gene symbol. It's pretty simple, the agent should be able to do it.

        Filter the GAF data by gene symbol.

        Args:
            gene_symbol: The gene symbol to filter by.
            qualifier: The qualifier to filter by.

        Returns:
            The filtered and simplified table.
        """
        # filter the data by gene symbol and optionally by qualifier
        q_df = self.data[self.data['DB_Object_Symbol'] == gene_symbol]
        if qualifier:
            q_df = q_df[q_df['Qualifier'] == qualifier]
        q_df['GO_annotation'] = q_df['GO_ID'].map(get_go_term_text)
        q_df['Evidence'] = q_df['Evidence'].map(evidence_codes)
        q_df['Gene'] = q_df['DB_Object_Symbol']
        return q_df[['Gene', 'Qualifier', 'GO_annotation', 'Evidence']].to_string(index=False)


def get_go_term_text(go_id: str) -> str:
    """
    Get the text description of a GO term.

    Args:
        go_id: The GO term ID.

    Returns:
        The text description of the GO term.
    """
    # make a request to get the text description of the GO term from QuickGO
    r = requests.get(f'https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{go_id}')
    data = r.json()
    return data['results'][0]['name']
