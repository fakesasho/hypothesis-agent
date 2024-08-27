from flaky import flaky
import json
import pytest

from ha.utils import clean_markdown_response


@pytest.mark.integration
def test_kegg_sanity_run(kegg):
    request = "Retrieve information about the DCC gene related to Colorectal cancer."
    goal_template = ('{"query": "<query here>", '
                     '"explanation": "<explanation here>"}, '
                     '"query_result": <result here or null for no result>}')
    r = kegg.run(request, goal_template=goal_template)
    response = json.loads(clean_markdown_response(r))
    print(response)
    assert response['query'], 'Query is missing.'
    assert response['explanation'], 'Explanation is missing.'
    assert response['query_result'], 'Query did not return any results.'


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
    "expected, case",
    [
        ('retrieved', 'Retrieve information about the DCC gene related to Colorectal cancer.'),
        ('retrieved', 'What genes are associated with Alzheimer disease?'),
        ('not_retrieved', "Is LRRK2 assiciated with Parkinson's disease?"),  # HS7: Sometimes win, sometimes lose
        ('not_retrieved', 'What gene NF11KMVJ2K associated with Colorectal cancer?'),
        # Add more cases as needed to trigger specific errors
    ]
)
@flaky(max_runs=5)
def test_kegg_run_cases(kegg, expected, case):
    goal_template = ('{"query": "<query here>", '
                     '"explanation": "<explanation here>"}, '
                     '"query_result": "<result here or null for no result>"}')
    r = kegg.run(case, goal_template=goal_template)
    response = json.loads(clean_markdown_response(r))

    if expected == 'retrieved':
        assert response['query'], 'Query is missing.'
        assert response['explanation'], 'Explanation is missing.'
        assert response['query_result'], 'Query did not return any results.'

    elif expected == 'not_retrieved':
        assert 'query' in response, 'Query is not present.'
        assert 'explanation' in response, 'Explanation is not present.'
        assert 'query_result' in response, 'Result is not present.'
        assert not response['query_result'], 'Query should not return any results.'
