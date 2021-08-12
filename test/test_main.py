import pytest

from photo_organiser import mp_main, argument_functions

# BAD_PARAMATERS = False

GOOD_INCOMING_PATH = "Y:\\photoOrganiser\\sample_data\\input"
GOOD_OUTPUT_PATH = "Y:\\photoOrganiser\\sample_data\\output"


@pytest.mark.parametrize(
    "arguments, expected_result",
    [
        (
            ["--input", GOOD_INCOMING_PATH, "--output", GOOD_OUTPUT_PATH],
            {
                "incoming_path": GOOD_INCOMING_PATH,
                "output_path": GOOD_OUTPUT_PATH,
            },
        ),
        (
            ["-i", GOOD_INCOMING_PATH, "-o", GOOD_OUTPUT_PATH],
            {
                "incoming_path": GOOD_INCOMING_PATH,
                "output_path": GOOD_OUTPUT_PATH,
            },
        ),
        (
            ["-i", "somebad in path", "-o", GOOD_OUTPUT_PATH],
            False,
        ),
        (
            ["-i", GOOD_INCOMING_PATH, "-o", "somebad out path"],
            False,
        ),
    ],
    ids=["good long args", "good short args", "bad incoming path", "bad output path"],
)
def test_validate_arguments(arguments, expected_result):
    assert argument_functions.validate_arguments(arguments) == expected_result


@pytest.mark.parametrize(
    "arguments, search_arguments, expected_result",
    [
        (
            ["--input", GOOD_INCOMING_PATH],
            ["--input"],
            GOOD_INCOMING_PATH,
        ),
        (
            ["--parameter", GOOD_INCOMING_PATH],
            ["--searchparameterthatdoesntexist"],
            GOOD_INCOMING_PATH,
        ),
    ],
    ids=["args present", "args not present"],
)
def test_get_arguments(arguments, search_arguments, expected_result):
    assert (
        argument_functions.validate_arguments(arguments, search_arguments)
        == expected_result
    )
