import json
import pytest

from ha.tools.gaf import Gaf
from ha.tools.graph import GraphAnalysis
from ha.tools.instructor import Instructor
from ha.tools.kegg import Kegg
from ha.tools.plan import PlanExecutor
from ha.agent.planner import Planner
from ha.neo4j import graphdb as driver


@pytest.fixture
def gaf():
    return Gaf()


@pytest.fixture
def kegg():
    return Kegg()


@pytest.fixture
def graphdb():
    return driver


@pytest.fixture
def plan_executor():
    return PlanExecutor()


@pytest.fixture
def planner():
    return Planner()


@pytest.fixture
def tool_registry():
    return PlanExecutor.tool_registry


@pytest.fixture
def conversations():
    with open('tests/data/conversations.json') as f:
        return json.load(f)


@pytest.fixture
def ga():
    return GraphAnalysis()

@pytest.fixture
def instructor():
    return Instructor()
