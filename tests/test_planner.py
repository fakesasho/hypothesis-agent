import json

from flaky import flaky
import pytest


@pytest.mark.integration
def test_planner_sanity_run(planner, tool_registry, conversations):
    response = planner.run(
        conversation=conversations['BRCA1'],
        objective='Turn how you would go about answering the first question into a multi-step "plan"'
    )
    print(response)
    assert response, 'The response is missing.'
    assert len(response) >= 1, f'The plan should have 3 steps. It has {len(response)} steps instead.'
    for i, item in enumerate(response):
        assert item['objective'], f'The instructions are missing. Item is: {i}'
        assert item['tool'], f'The goal template is missing. Item is: {i}'
        assert item['tool'] in tool_registry, f'The tool is not in the tool registry. Item is: {i}'


@pytest.mark.slow
@pytest.mark.integration
@pytest.mark.parametrize(
    "conversation_name, objective",
    [
        ('TP53', 'Turn how you would go about answering the first question into a multi-step "plan". '
                 'Break the steps down to single query steps if you need to.'),
        ('BRCA1', 'Turn how you would go about answering the first question into a multi-step "plan"'),
        # Add more cases as needed to trigger specific stuff
    ]
)
@flaky(max_runs=5)
def test_planner_run_cases(planner, tool_registry, conversations, conversation_name, objective):
    conversation = conversations[conversation_name]
    response = planner.run(
        conversation=conversation,
        objective=objective
    )
    assert response, 'The response is missing.'
    assert len(response) >= 1, f'The plan should have 3 steps. It has {len(response)} steps instead.'
    for i, item in enumerate(response):
        assert item['objective'], f'The instructions are missing. Item is: {i}'
        assert item['tool'], f'The goal template is missing. Item is: {i}'
        assert item['tool'] in tool_registry, f'The tool is not in the tool registry. Item is: {i}'
