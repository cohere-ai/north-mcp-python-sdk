from north_mcp_python_sdk.types import NorthResult


def test_north_result_no_metadata():
    """Tests that NorthResult initializes correctly with no metadata."""
    result = NorthResult(value={"data": 123})
    expected_dict = {"result": {"data": 123}}
    assert result == expected_dict


def test_north_result_only_title():
    """Tests that NorthResult initializes correctly with only a title."""
    result = NorthResult(value={"data": 456}, title="My Title")
    expected_dict = {
        "result": {"data": 456},
        "_north_metadata": {"title": "My Title"},
    }
    assert result == expected_dict


def test_north_result_only_content():
    """Tests that NorthResult initializes correctly with only content."""
    result = NorthResult(value={"data": 789}, content="My content")
    expected_dict = {
        "result": {"data": 789},
        "_north_metadata": {"content": "My content"},
    }
    assert result == expected_dict


def test_north_result_with_all_metadata():
    """Tests that NorthResult initializes correctly with all metadata."""
    result = NorthResult(value={"data": "abc"}, title="Full Title", content="Full content")
    expected_dict = {
        "result": {"data": "abc"},
        "_north_metadata": {"title": "Full Title", "content": "Full content"},
    }
    assert result == expected_dict
