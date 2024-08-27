from flaky import flaky
import json
import pytest


@pytest.mark.integration
def test_instructor_sanity_run(instructor, kegg):
    objective = "Is DCC gene related to Colorectal cancer?"
    tool = json.dumps({
        "name": "kegg_query",
        "description": "KEGG is a database of diseaase pathways stored in a Neo4j instance."
                       "The tool allows you to use Cypher queries to retrieve information about the signaling"
                       "between genes in a disease pathway."
    })
    response = instructor.run(objective=objective, tool=tool, schema=kegg.get_schema())
    assert response['instructions'], 'The instructions are missing.'
    assert response['goal_template'], 'The goal template is missing.'


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
    "objective, tool",
    [
        ('How many proteins are associated with the DCC gene?',
         json.dumps({
                "name": "gaf_query",
                "description": "The GAF database instance contains GO terms and annotations for "
                               "human genes. The tool allows queries using SQLite and the "
                               "standard GAF file headings."
            })),
        # Add more cases as needed to trigger specific errors
    ]
)
@flaky(max_runs=5)
def test_instructor_run_cases(instructor, objective, tool):
    response = instructor.run(objective=objective, tool=tool)
    assert response['instructions'], 'The instructions are missing.'
    assert response['goal_template'], 'The goal template is missing.'
