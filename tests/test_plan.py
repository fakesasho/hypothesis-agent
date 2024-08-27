from flaky import flaky
import pytest


@pytest.mark.integration
def test_plan_executor_sanity_run(plan_executor):
    plan = [
        {
            "tool": "kegg_query",
            "objective": "Retrieve information about the DCC gene related to Colorectal cancer."
        },
        {
            "tool": "gaf_query",
            "objective": "How many proteins are associated with the DCC gene?"
        }
    ]
    response = plan_executor.run(plan=plan)
    assert response, 'The response is missing.'
    assert len(response) == len(plan), f'The response should have {len(plan)} items. It has {len(response)} items.'
    for i, item in enumerate(response):
        assert item['instructions'], f'The instructions are missing. Item is: {i}'
        assert item['response'], f'The goal template is missing. Item is: {i}'
        assert item['feedback'], f'The feedback is missing. Item is: {i}'


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
    "plan",
    [
        [
            {
                "tool": "gaf_query",
                "objective": "Filter the GAF file to retrieve all rows where `DB_Object_Symbol (Column 3)` equals 'BRCA1'."
            },
            {
                "tool": "gaf_query",
                "objective": "Extract the `GO_ID (Column 5)` and `Evidence_Code (Column 7)` from the filtered rows."
            },
            {
                "tool": "gaf_query",
                "objective": "Identify and list GO terms (`GO_ID`) that have strong experimental evidence by focusing on evidence codes like EXP, IDA, and IMP."
            }
        ],
        [
            {
              "tool": "gaf_query",
              "objective": "Filter the GAF file to retrieve all rows where `DB_Object_Symbol (Column 3)` equals 'BRCA1'."
            },
            {
              "tool": "gaf_query",
              "objective": "Extract the `GO_ID (Column 5)` associated with BRCA1."
            },
            {
              "tool": "gaf_query",
              "objective": "Search the GAF file for other genes (`DB_Object_Symbol (Column 3)`) that are annotated with the same `GO_ID (Column 5)` values."
            }
        ],
        # Add more cases as needed to trigger specific
    ]
)
@flaky(max_runs=5)
def test_instructor_run_cases(plan_executor, plan):
    response = plan_executor.run(plan=plan)
    print(response)
    assert response, 'The response is missing.'
    assert len(response) == len(plan), f'The response should have {len(plan)} items. It has {len(response)} items.'
    for i, item in enumerate(response):
        assert item['instructions'], f'The instructions are missing. Item is: {i}'
        assert item['response'], f'The goal template is missing. Item is: {i}'
        assert item['feedback'], f'The feedback is missing. Item is: {i}'
