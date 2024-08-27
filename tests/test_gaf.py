import json

import pytest
import requests
from unittest.mock import patch

from ha.tools.gaf import get_go_term_text
from ha.utils import clean_markdown_response


@patch('requests.get')
def test_get_go_term_text_success(mock_get):
    # Mock the GET request to return a successful response with the mock data
    mock_get.return_value.json.return_value = {
        'results': [
            {'name': 'mock_GO_term_name'}
        ]
    }

    # Call the function with a test GO term ID
    go_id = 'GO:0008150'
    result = get_go_term_text(go_id)

    # Assert that the result is the name of the GO term from the mock data
    assert result == 'mock_GO_term_name'
    # Ensure that the request was made with the correct URL
    mock_get.assert_called_once_with(f'https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{go_id}')


@patch('requests.get')
def test_get_go_term_text_failure(mock_get):
    # Mock the GET request to return an empty results list (simulate failure)
    mock_get.return_value.json.return_value = {
        'results': []
    }

    # Call the function with a test GO term ID
    go_id = 'GO:0000000'
    with pytest.raises(IndexError):
        # Assuming an IndexError would be raised due to the empty 'results' list
        get_go_term_text(go_id)

    # Ensure that the request was made with the correct URL
    mock_get.assert_called_once_with(f'https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{go_id}')


@patch('requests.get')
def test_get_go_term_text_http_error(mock_get):
    # Simulate an HTTP error (e.g., 404 Not Found)
    mock_get.side_effect = requests.exceptions.HTTPError

    go_id = 'GO:0000000'
    with pytest.raises(requests.exceptions.HTTPError):
        get_go_term_text(go_id)

    # Ensure that the request was made with the correct URL
    mock_get.assert_called_once_with(f'https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{go_id}')


@pytest.mark.integration
def test_gaf_run_sanity(gaf):
    goal_template = ('{"query": "<query here>", '
                     '"explanation": "<explanation here>"}, '
                     '"query_result": <verbatim result here or null for no result>}')
    request = "Retrieve information about the DCC gene."
    r = gaf.run(request, goal_template=goal_template)
    response = json.loads(clean_markdown_response(r))
    assert response['query'], 'Query is missing.'
    assert response['explanation'], 'Explanation is missing.'
    assert response['query_result'], 'Query did not return any results.'


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
    "expected, case",
    [
        ('retrieved', 'Retrieve information about the DCC gene.'),
        ('retrieved', 'What does the DCC gene enable?'),
        ('not_retrieved', 'Are tehre any GO annotations where NALF2 has the enables qualifier?'),
        ('not_retrevied', 'What gene is associated with Alzheimer disease?')
    ]
)
def test_gaf_run_cases(gaf, expected, case):
    goal_template = ('{"query": "<query here>", '
                     '"explanation": "<explanation here>"}, '
                     '"query_result": <verbatim result here or null for no result>}')
    r = gaf.run(case, goal_template=goal_template)
    print(r)
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
