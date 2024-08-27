import json
import pytest

from ha.tools.graph import GraphAnalysis


@pytest.mark.integration
def test_get_directly_impacted_nodes():
    # Inputs for the method
    node_name = "INSR"
    pathway_title = "Type II diabetes mellitus"

    # Expected output
    expected_result = ['MAPK1', 'IRS1']

    # Call the method
    result = GraphAnalysis.get_directly_impacted_nodes(node_name, pathway_title)

    # Assertions
    print(result)
    assert result == expected_result


@pytest.mark.integration
def test_get_roots_to_node_distances():
    # Define the test parameters
    node_name = "INSR"
    pathway_title = "Type II diabetes mellitus"

    # Expected results (min and max distances)
    expected_min_distance = 1
    expected_max_distance = 3

    # Call the function with the test parameters
    result = GraphAnalysis.get_roots_to_node_distances(node_name, pathway_title)

    # Verify the results
    assert result[
               'min_distance'] == expected_min_distance, (f"Expected min distance {expected_min_distance}, "
                                                          f"but got {result['min_distance']}")
    assert result[
               'max_distance'] == expected_max_distance, (f"Expected max distance {expected_max_distance}, "
                                                          f"but got {result['max_distance']}")


@pytest.mark.integration
def test_get_node_subtree_depths():
    # Define the test input
    pathway_title = "Type II diabetes mellitus"
    node_name = "INSR"

    # Expected output (these values are what you expect the test to return)
    expected_min_distance = 3
    expected_max_distance = 4

    # Call the method under test
    result = GraphAnalysis.get_node_subtree_depths(node_name, pathway_title)

    # Assert the results are as expected
    assert result[
               'min_distance'] == expected_min_distance, (f"Expected min distance {expected_min_distance}, "
                                                          f"but got {result['min_distance']}")
    assert result[
               'max_distance'] == expected_max_distance, (f"Expected max distance {expected_max_distance}, "
                                                          f"but got {result['max_distance']}")


@pytest.mark.integration
def test_get_root_depths():
    # Define the test input
    pathway_title = "Type II diabetes mellitus"

    # Expected output (these values are what you expect the test to return)
    expected_min_distance = 1
    expected_max_distance = 7

    # Call the method under test
    result = GraphAnalysis.get_root_depths(pathway_title)

    # Assert the results are as expected
    assert result[
               'min_distance'] == expected_min_distance, (f"Expected min distance {expected_min_distance}, "
                                                          f"but got {result['min_distance']}")
    assert result[
               'max_distance'] == expected_max_distance, (f"Expected max distance {expected_max_distance}, "
                                                          f"but got {result['max_distance']}")


@pytest.mark.integration
def test_forest_subarea_ratio():
    # Define the test inputs
    node_name = "INSR"
    pathway_title = "Type II diabetes mellitus"

    # Expected output (approximate value)
    expected_ratio = 0.03

    # Tolerance threshold
    threshold = 0.01

    # Call the method under test
    result = GraphAnalysis.forest_subarea_ratio(node_name, pathway_title)

    # Check if the result is within the acceptable range
    assert abs(
        result - expected_ratio) <= threshold, (f"Expected ratio close to {expected_ratio} within {threshold}, "
                                                f"but got {result}")

@pytest.mark.integration
def test_graph_analysis_sanity_run(ga):
    instructions = "What is the impact of INSR gene on Type II diabetes mellitus pathway?"
    response = json.loads(ga.run(instructions=instructions))
    print(response)
    assert response['node_name'] == 'INSR', "node_name is not as expected"
    assert response['pathway_title'] == 'Type II diabetes mellitus', "pathway_title is not as expected"
    assert response['forest_subarea_ratio'] - 0.03 < 0.01, "forest_subarea_ratio is not as expected"
    assert response['root_to_node'] == [1, 3], "Root to node distances are not as expected"
    assert response['root_to_leaf'] == [1, 7], "Root to leaf distances are not as expected"
    assert response['node_to_leaf'] == [3, 4], "Node to leaf distances are not as expected"
    assert response['directly_impacted_nodes'] == ['MAPK1', 'IRS1'], "Directly impacted nodes are not as expected"
